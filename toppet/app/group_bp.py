# app/group_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import date, datetime # Added datetime for precise timestamps
from sqlalchemy import func, and_

from . import db
from .models import Group, GroupMember, PetImage, User, Vote, VotingRound # NEW: Import VotingRound

group_bp = Blueprint('group_bp', __name__)

def allowed_file(filename):
    if not filename:
        return False
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']

def get_current_voting_round(group_id):
    """Fetches the current active voting round for a given group."""
    # A round is "current" if it exists and has no end_time
    return VotingRound.query.filter(
        VotingRound.group_id == group_id,
        VotingRound.end_time.is_(None)
    ).first()

def create_new_voting_round(group_id):
    """Creates a new voting round for a group."""
    last_round = VotingRound.query.filter_by(group_id=group_id).order_by(VotingRound.round_number.desc()).first()
    new_round_number = (last_round.round_number + 1) if last_round else 1
    
    new_round = VotingRound(
        group_id=group_id,
        round_number=new_round_number,
        start_time=datetime.now()
    )
    db.session.add(new_round)
    db.session.commit()
    return new_round

def end_voting_round(group_id, current_round_id):
    """
    Ends the current voting round, determines a winner, and updates scores.
    Returns True if a winner was found and updated, False otherwise.
    """
    current_round = VotingRound.query.get(current_round_id)
    if not current_round:
        return False

    current_round.end_time = datetime.now()

    # Get all images uploaded during this round
    round_images = PetImage.query.filter(
        PetImage.group_id == group_id,
        PetImage.round_id == current_round_id
    ).order_by(PetImage.votes_count.desc()).all()

    if not round_images:
        # No images, no winner
        current_round.winner_id = None
        current_round.winning_image_id = None
        db.session.commit()
        return False, "No images were uploaded for this round."

    # Determine winner(s)
    max_votes = -1
    winning_images = []
    
    # Find the maximum votes
    for img in round_images:
        if img.votes_count > max_votes:
            max_votes = img.votes_count
            
    # Collect all images with max_votes (handle ties)
    for img in round_images:
        if img.votes_count == max_votes:
            winning_images.append(img)
    
    if max_votes == 0:
        # No votes cast for any image, no winner
        current_round.winner_id = None
        current_round.winning_image_id = None
        db.session.commit()
        return False, "No votes were cast for any image this round."


    if len(winning_images) == 1:
        # Clear winner
        winner_image = winning_images[0]
        winner_user = User.query.get(winner_image.user_id)
        if winner_user:
            winner_user.total_wins += 1 # Increment global win count
            db.session.add(winner_user)
            current_round.winner_id = winner_user.id
            current_round.winning_image_id = winner_image.id
            db.session.commit()
            return True, {
                'username': winner_user.userName,
                'votes': winner_image.votes_count,
                'image_filename': winner_image.filename,
                'image_url': url_for('static', filename='uploads/' + winner_image.filename),
                'message': f"The winner for this round is {winner_user.userName} with {winner_image.votes_count} votes!"
            }
    else:
        # Tie
        # For simplicity, if there's a tie, we'll declare it a draw for now.
        # You could implement tie-breaking rules (e.g., earliest upload, random).
        current_round.winner_id = None
        current_round.winning_image_id = None
        db.session.commit()
        tied_users = ", ".join([User.query.get(img.user_id).userName for img in winning_images])
        return False, f"It's a tie with {max_votes} votes! Participants: {tied_users}"

    db.session.commit()
    return False, "Could not determine a unique winner." # Should not be reached if logic is sound


# --- Routes for Group Management ---

@group_bp.route('/groups')
@login_required
def list_groups():
    groups = Group.query.all()
    user_memberships = {member.group_id for member in current_user.group_memberships}
    
    # Global Leaderboard
    leaderboard = User.query.order_by(User.total_wins.desc()).limit(10).all()

    return render_template('groups.html',
                           groups=groups,
                           user_memberships=user_memberships,
                           leaderboard=leaderboard)

@group_bp.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        group_name = request.form.get('group_name')
        if not group_name:
            flash('Group name cannot be empty!', 'error')
            return redirect(url_for('group_bp.create_group'))

        existing_group = Group.query.filter_by(name=group_name).first()
        if existing_group:
            flash('A group with this name already exists.', 'error')
            return redirect(url_for('group_bp.create_group'))

        new_group = Group(name=group_name, creator_id=current_user.id)
        db.session.add(new_group)
        db.session.commit()

        # Make the creator a member automatically
        member = GroupMember(user_id=current_user.id, group_id=new_group.id)
        db.session.add(member)
        db.session.commit()

        # Also create the first voting round for the new group
        create_new_voting_round(new_group.id)

        flash(f'Group "{group_name}" created successfully!', 'success')
        return redirect(url_for('group_bp.group_detail', group_id=new_group.id))
    return render_template('create_group.html')

@group_bp.route('/join_group/<int:group_id>')
@login_required
def join_group(group_id):
    group = Group.query.get_or_404(group_id)
    existing_member = GroupMember.query.filter_by(user_id=current_user.id, group_id=group_id).first()

    if existing_member:
        flash(f'You are already a member of "{group.name}".', 'info')
    else:
        member = GroupMember(user_id=current_user.id, group_id=group_id)
        db.session.add(member)
        db.session.commit()
        flash(f'You have joined "{group.name}"!', 'success')
    return redirect(url_for('group_bp.group_detail', group_id=group_id))


@group_bp.route('/vote_image/<int:image_id>', methods=['POST'])
@login_required
def vote_image(image_id):
    image = PetImage.query.get_or_404(image_id)
    group = image.group_images # Access the group through the relationship
    
    current_round = get_current_voting_round(group.id)

    if not current_round:
        return jsonify({'success': False, 'message': "No active voting round. Please wait for a new round to begin."}), 400

    # Ensure user is a member of the group
    is_member = GroupMember.query.filter_by(user_id=current_user.id, group_id=group.id).first()
    if not is_member:
        return jsonify({'success': False, 'message': "You are not a member of this group."}), 403

    # Prevent user from voting on their own image
    if image.user_id == current_user.id:
        return jsonify({'success': False, 'message': "You cannot vote on your own image."}), 403

    # Check if the image belongs to the current round
    if image.round_id != current_round.id:
        return jsonify({'success': False, 'message': "This image is not part of the current voting round."}), 400

    # Find if the user has already cast a vote in the current round
    existing_vote_in_round = Vote.query.filter(
        Vote.user_id == current_user.id,
        Vote.round_id == current_round.id
    ).first()

    message = ""
    success = False
    has_voted_on_this_image = False
    old_voted_image_id = None
    old_votes_count = None
    
    # Track if round ends due to this vote
    game_ended_early = False
    winner_info = None

    if existing_vote_in_round:
        if existing_vote_in_round.pet_image_id == image_id:
            # Case 1: User already voted for THIS image in this round -> Unvote
            db.session.delete(existing_vote_in_round)
            image.votes_count -= 1
            message = "Vote removed successfully!"
            success = True
            has_voted_on_this_image = False
        else:
            # Case 2: User voted for a DIFFERENT image in this round -> Change vote (transfer)
            old_image = PetImage.query.get(existing_vote_in_round.pet_image_id)
            if old_image:
                old_image.votes_count -= 1
                old_voted_image_id = old_image.id
                old_votes_count = old_image.votes_count
            
            db.session.delete(existing_vote_in_round)
            
            new_vote = Vote(user_id=current_user.id, pet_image_id=image_id, round_id=current_round.id)
            db.session.add(new_vote)
            image.votes_count += 1
            message = "Vote changed successfully!"
            success = True
            has_voted_on_this_image = True
    else:
        # Case 3: No vote cast by user in this round -> New vote
        new_vote = Vote(user_id=current_user.id, pet_image_id=image_id, round_id=current_round.id)
        db.session.add(new_vote)
        image.votes_count += 1
        message = "Image liked!"
        success = True
        has_voted_on_this_image = True
    
    db.session.commit()

    # Check if all members have voted after this action
    group_members = GroupMember.query.filter_by(group_id=group.id).all()
    member_ids = {m.user_id for m in group_members}
    
    # Get all distinct user_ids who have voted in the current round
    voted_member_ids = {v.user_id for v in Vote.query.filter_by(round_id=current_round.id).all()}
    
    # Get all users who have uploaded an image in this round
    # Only members who uploaded an image are expected to vote, unless we allow all members to vote
    # Based on the prompt "all group members have cast their vote", we assume all group members need to vote.
    
    # Filter out users who haven't uploaded an image, as they can't vote.
    # No, the prompt says "all group members". If a member hasn't uploaded, they still need to vote on others'.
    # This means the game can only end if all members capable of voting (i.e., not themselves) have voted.
    # If a member hasn't uploaded an image and hasn't voted on others' images, they still count as "not voted".
    
    # Determine which members ARE eligible to vote (i.e., not the uploader of their own image, or any image if they haven't uploaded)
    
    # Let's re-evaluate the "all group members have cast their vote".
    # This implies every single member of the group must vote. If a member hasn't uploaded, they vote on one of the others.
    # If a member *has* uploaded, they vote on one of the *other* images.
    
    # All members who are not the current round's image uploader for their own image.
    
    # Simplest interpretation of "all group members have cast their vote":
    # Count the number of members in the group.
    # Count the number of unique votes cast in the current round.
    # If these numbers match AND there are at least 3 members, the round ends.

    num_members = len(member_ids)
    num_voted_members = len(voted_member_ids)

    # Check the minimum members for round to start/end
    if num_members < 3:
        # This should ideally be checked when creating/joining a group or starting a round,
        # but as a safeguard, prevent round end if not enough members.
        pass # Round won't end if not enough members, voting continues.

    # Check if all *eligible* members have voted.
    # "all group members have cast their vote".
    # We need to refine this: "all group members who are able to vote in the current round have voted".
    # This means, a member who uploaded an image cannot vote for their own.
    # A member who did NOT upload an image, can vote for any image.

    # Let's consider the set of members who are required to vote:
    # All members minus any member who is the sole uploader of an image in the round (and thus can't vote).
    
    # For now, stick to the direct interpretation: num_members == num_voted_members
    # This means *everyone* has to cast a vote, even if they didn't upload an image.
    # It implies a user who uploaded an image must vote for another image.
    # This is consistent with the `if image.user_id == current_user.id:` check.

    if num_voted_members == num_members and num_members >= 3:
        # All members have voted! End the round.
        game_ended_early = True
        did_win, result_info = end_voting_round(group.id, current_round.id)
        if did_win:
            winner_info = result_info
            message = "All members have voted! Round ended. " + winner_info['message']
        else:
            message = "All members have voted! Round ended. " + result_info

        # Create a new round immediately for the next game
        create_new_voting_round(group.id)


    response_data = {
        'success': success,
        'message': message,
        'votes_count': image.votes_count,
        'has_voted': has_voted_on_this_image,
        'game_ended_early': game_ended_early, # New flag for JS
        'winner_info': winner_info # New data for JS if game ended
    }
    if old_voted_image_id:
        response_data['old_voted_image_id'] = old_voted_image_id
        response_data['old_votes_count'] = old_votes_count
    
    # Also include voting status for the banner (re-calculate on every vote)
    member_vote_statuses = []
    all_group_members = GroupMember.query.filter_by(group_id=group.id).all()
    for member_ship in all_group_members:
        member_user = User.query.get(member_ship.user_id)
        has_voted_this_round = Vote.query.filter(
            Vote.user_id == member_ship.user_id,
            Vote.round_id == current_round.id if current_round else None # Check against current round
        ).first() is not None
        member_vote_statuses.append({
            'username': member_user.userName,
            'has_voted': has_voted_this_round
        })
    response_data['member_vote_statuses'] = member_vote_statuses

    return jsonify(response_data)


@group_bp.route('/group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    is_member = GroupMember.query.filter_by(user_id=current_user.id, group_id=group_id).first()

    if not is_member:
        flash("You are not a member of this group.", "error")
        return redirect(url_for('group_bp.list_groups'))

    group_memberships = GroupMember.query.filter_by(group_id=group.id).all()
    num_members = len(group_memberships)
    min_members_met = (num_members >= 3) # NEW: Check minimum member count

    current_round = get_current_voting_round(group.id)
    
    # If there's no current round, and we have enough members, create one.
    # This handles the case where the app is restarted or a group is old and needs a new round.
    if not current_round and min_members_met:
        current_round = create_new_voting_round(group.id)
        flash("A new voting round has started!", "info")
    elif not current_round and not min_members_met:
        flash(f"Group needs at least 3 members to start a voting round. Current members: {num_members}", "warning")


    # Logic for past winner display
    past_winner_info = None
    last_completed_round = VotingRound.query.filter(
        VotingRound.group_id == group.id,
        VotingRound.end_time.isnot(None)
    ).order_by(VotingRound.end_time.desc()).first()

    if last_completed_round:
        if last_completed_round.winner_id and last_completed_round.winning_image_id:
            winner_user = User.query.get(last_completed_round.winner_id)
            winning_image = PetImage.query.get(last_completed_round.winning_image_id)
            if winner_user and winning_image:
                past_winner_info = {
                    'username': winner_user.userName,
                    'votes': winning_image.votes_count,
                    'image_filename': winning_image.filename,
                    'image_url': url_for('static', filename='uploads/' + winning_image.filename),
                    'round_number': last_completed_round.round_number
                }
        else:
            past_winner_info = {
                'message': "No winner determined for the last round (it might have been a tie or no votes).",
                'round_number': last_completed_round.round_number
            }
        
    
    # --- Image Upload Logic ---
    already_uploaded_this_round = None
    if current_round:
        already_uploaded_this_round = PetImage.query.filter(
            PetImage.user_id == current_user.id,
            PetImage.group_id == group.id,
            PetImage.round_id == current_round.id
        ).first()

    if request.method == 'POST':
        if not min_members_met:
            flash(f"Cannot upload image. Group needs at least 3 members to start a voting round. Current members: {num_members}", "error")
            return redirect(request.url)
            
        if not current_round:
            flash("Cannot upload image. No active voting round. This might happen if the group is new and doesn't meet minimum members, or a round just ended.", "error")
            return redirect(request.url)

        if 'pet_image' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['pet_image']

        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file type. Allowed: png, jpg, jpeg, gif', 'error')
            return redirect(request.url)

        if already_uploaded_this_round:
            flash('You can only upload one image per round to this group.', 'error')
            return redirect(request.url)

        if file:
            timestamp_str = datetime.now().strftime('%Y%m%d%H%M%S%f')
            filename = secure_filename(f"{current_user.id}_{group.id}_{current_round.id}_{timestamp_str}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            try:
                file.save(filepath)
            except Exception as e:
                flash(f"Error saving image: {e}", "error")
                return redirect(request.url)

            new_image = PetImage(
                filename=filename,
                user_id=current_user.id,
                group_id=group.id,
                uploaded_at=datetime.now(),
                votes_count=0,
                round_id=current_round.id # Assign image to the current round
            )
            db.session.add(new_image)
            db.session.commit()
            flash('Image uploaded successfully!', 'success')
            return redirect(url_for('group_bp.group_detail', group_id=group.id))

    # --- Fetch images for current round display ---
    group_images = []
    if current_round:
        group_images = PetImage.query.filter(
            PetImage.group_id == group.id,
            PetImage.round_id == current_round.id
        ).order_by(PetImage.votes_count.desc(), PetImage.uploaded_at.desc(), PetImage.id.desc()).all()


    images_for_template = []
    user_voted_image_id_this_round = None
    
    if current_round:
        user_vote_obj_this_round = Vote.query.filter(
            Vote.user_id == current_user.id,
            Vote.round_id == current_round.id
        ).first()
        
        if user_vote_obj_this_round:
            user_voted_image_id_this_round = user_vote_obj_this_round.pet_image_id

    for img in group_images:
        uploader = User.query.get(img.user_id)
        is_uploader = (current_user.id == img.user_id)
        images_for_template.append({
            'id': img.id,
            'filename': img.filename,
            'uploaded_at': img.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
            'uploader_name': uploader.userName if uploader else 'Unknown',
            'full_url': url_for('static', filename='uploads/' + img.filename),
            'votes': img.votes_count,
            'has_voted': (img.id == user_voted_image_id_this_round),
            'is_uploader': is_uploader
        })

    # --- Member Vote Status for Banner ---
    member_vote_statuses = []
    all_group_members = GroupMember.query.filter_by(group_id=group.id).all()
    for member_ship in all_group_members:
        member_user = User.query.get(member_ship.user_id)
        has_voted_this_round = False
        if current_round:
            has_voted_this_round = Vote.query.filter(
                Vote.user_id == member_ship.user_id,
                Vote.round_id == current_round.id
            ).first() is not None
        member_vote_statuses.append({
            'username': member_user.userName,
            'has_voted': has_voted_this_round
        })


    return render_template('group_detail.html',
        group=group,
        images=images_for_template,
        already_uploaded_this_period=already_uploaded_this_round, # Renamed for clarity
        current_round_num=current_round.round_number if current_round else 0, # Pass current round number
        past_winner_info=past_winner_info, # Pass last round's winner info
        member_vote_statuses=member_vote_statuses, # Pass member vote status
        min_members_met=min_members_met # Pass boolean for min members check
    )