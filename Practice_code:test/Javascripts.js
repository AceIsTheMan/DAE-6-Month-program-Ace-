// Safely pull the ID passed from Python/Django JSON tag
const videoId = JSON.parse(document.getElementById('yt-video-id').textContent);
let player;

// 1. This function automatically fires when the YouTube API script loads
function onYouTubeIframeAPIReady() {
    player = new onYouTubeIframeAPIReady.Player('player', {
        height: '0',
        width: '0',
        videoId: videoId,
        playerVars: {
            'autoplay': 0,          // Handled manually by user gesture
            'controls': 0,          // No visible UI controls needed
            'loop': 1,              // Tells it to prepare loop parameters
            'playlist': videoId,    // Required parameter for loops to execute on YT embeds
            'modestbranding': 1
        },
        events: {
            'onReady' : onPlayerReady,
            'onStateChange' : onPlayerStateChange
        }
    });
}

function onPlayerReady(event) {
    // Player is mounted off-screen and ready to go
    const startButton = document.getElementById('start-btn');
    const overlay = document.getElementById('welcome-overlay');

    startButton.addEventListener('click', () => {
        // Play the track now that browser has tracked an explicit click gesture
        player.playVideo();

        // Hide overlay smoothly
        overlay.style.opacity = '0';
        setTimeout(() => overlay.style.display = 'none' , 500);
    });
}
// 