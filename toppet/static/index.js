// app/static/index.js

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded. Initializing script.'); // Added for debugging

    // Function to reload page to show updated game state (winner, new round)
    function reloadPageForGameState() {
        window.location.reload();
    }

    // Function to update the member status banner
    function updateMemberStatusBanner(memberStatuses) {
        const banner = document.getElementById('member-status-banner');
        if (!banner) return;

        banner.innerHTML = ''; // Clear existing members

        memberStatuses.forEach(member => {
            const span = document.createElement('span');
            span.classList.add('list-group-item', 'list-group-item-action');
            if (member.has_voted) {
                span.classList.add('member-voted');
                span.textContent = `${member.username} ✅`;
            } else {
                span.classList.add('member-not-voted');
                span.textContent = `${member.username} ⚪`;
            }
            banner.appendChild(span);
        });
    }

    const imageGrid = document.getElementById('image-grid');
    console.log('Image grid element:', imageGrid); // Added for debugging

    if (imageGrid) {
        imageGrid.addEventListener('click', function(event) {
            console.log('Click event detected on imageGrid!'); // Added for debugging
            let targetCard = event.target.closest('.image-card-clickable-container');
            
            if (!targetCard) {
                console.log('Click was not on a clickable container. Returning.'); // Added for debugging
                return; // Click was not on an image card container
            }
            console.log('Clickable container found:', targetCard); // Added for debugging

            const imageId = targetCard.dataset.imageId;
            const isUploader = targetCard.dataset.isUploader === 'true';
            console.log('Image ID:', imageId, 'Is Uploader:', isUploader); // Added for debugging

            // IMPORTANT: If you re-enabled the minMembersMet check, it might be the cause.
            // If you did add the hidden input as suggested, then you can uncomment this block.
            // Otherwise, keep it commented out for testing.
            /*
            const minMembersMet = document.getElementById('min-members-met-flag') ? document.getElementById('min-members-met-flag').value === 'true' : false;
            console.log('minMembersMet:', minMembersMet); // Added for debugging
            if (!minMembersMet) {
                alert("Cannot vote. Group needs at least 3 members to start a voting round.");
                return;
            }
            */
            
            if (isUploader) {
                alert("You cannot vote on your own image.");
                return;
            }

            const votesSpan = document.getElementById(`votes-${imageId}`);
            console.log('Votes Span for image:', votesSpan); // Added for debugging

            fetch(`/vote_image/${imageId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
            })
            .then(response => {
                console.log('Fetch response received:', response); // Added for debugging
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log('Fetch data received:', data); // Added for debugging
                if (data.success) {
                    const currentImageCard = document.querySelector(`.image-card-clickable-container[data-image-id="${imageId}"]`);
                    if (currentImageCard && votesSpan) {
                        votesSpan.textContent = data.votes_count;
                        
                        if (data.has_voted) {
                            currentImageCard.classList.add('voted');
                        } else {
                            currentImageCard.classList.remove('voted');
                        }
                    }

                    if (data.old_voted_image_id) {
                        const oldImageCard = document.querySelector(`.image-card-clickable-container[data-image-id="${data.old_voted_image_id}"]`);
                        const oldVotesSpan = document.getElementById(`votes-${data.old_voted_image_id}`);
                        if (oldImageCard && oldVotesSpan) {
                            oldImageCard.classList.remove('voted');
                            oldVotesSpan.textContent = data.old_votes_count;
                        }
                    }

                    if (data.member_vote_statuses) {
                        updateMemberStatusBanner(data.member_vote_statuses);
                    }

                    if (data.game_ended_early) {
                        alert(data.message || "Round ended!");
                        reloadPageForGameState();
                    }

                } else {
                    alert(data.message || 'Could not process vote.');
                    if (data.message && (data.message.includes("No active voting round") || data.message.includes("Voting for this period has ended"))) {
                         reloadPageForGameState();
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred during voting: ' + error.message);
                reloadPageForGameState();
            });
        });
    }

    // Reminder: Add the hidden input for min_members_met to group_detail.html if you want this JS check to work accurately:
    // <input type="hidden" id="min-members-met-flag" value="{{ 'true' if min_members_met else 'false' }}">
});