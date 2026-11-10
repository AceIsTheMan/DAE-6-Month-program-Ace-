// Safely pull the ID passed from Python/Django JSON tag
const videoIdElement = document.getElementById('yt-video-id');
const videoId = videoIdElement ? JSON.parse(videoIdElement.textContent) : 'MoPCsL5S6S4';
let player;

// 1. This function automatically fires when the YouTube API script loads
function onYouTubeIframeAPIReady() {
    player = new YT.Player('player', {
        height: '1', // Setting to 1px bypasses certain browser engine rendering blocks
        width: '1',
        videoId: videoId,
        playerVars: {
            'autoplay': 1,        // Pre-initialize stream pipeline data
            'mute': 1,            // Start muted so browser engine NEVER blocks initial load
            'controls': 0,        // No visible UI controls needed
            'loop': 1,            // Tells it to prepare loop parameters
            'playlist': videoId,   // Required parameter for loops to execute on YT embeds
            'enablejsapi': 1      // Strictly required for tab communication controls
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange
        }
    });
}

function onPlayerReady(event) {
    const startButton = document.getElementById('start-btn');
    const overlay = document.getElementById('welcome-overlay');
    const musicToggle = document.getElementById('music-toggle');

    // Handle initial entrance click behavior
    if (startButton) {
        startButton.addEventListener('click', () => {
            // Unmute on explicit user click gesture to trigger background play safely
            if (musicToggle && musicToggle.checked) {
                player.unmute();
                player.setVolume(50); // Set baseline volume level (0-100)
                player.playVideo();
            }
            
            if (overlay) {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.style.display = 'none', 500);
            }
        });
    }

    // Monitor live configuration switches in the options tab dashboard
    if (musicToggle) {
        musicToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                player.unmute();
                player.playVideo(); 
            } else {
                player.mute();
            }
        });
    }
}

// 2. Fallback protection loop for short tracks or single-video loops
function onPlayerStateChange(event) {
    if (event.data === YT.PlayerState.ENDED) {
        player.playVideo();
    }
}
// // Safely pull the ID passed from Python/Django JSON tag
// const videoId = JSON.parse(document.getElementById('yt-video-id').textContent);
// let player;

// // 1. This function automatically fires when the YouTube API script loads
// function onYouTubeIframeAPIReady() {
//     player = new YT.Player('player', {
//         height: '0',
//         width: '0',
//         videoId: videoId,
//         playerVars: {
//             'autoplay': 0,          // Handled manually by user gesture
//             'controls': 0,          // No visible UI controls needed
//             'loop': 1,              // Tells it to prepare loop parameters
//             'playlist': videoId,    // Required parameter for loops to execute on YT embeds
//             'modestbranding': 1
//         },
//         events: {
//             'onReady' : onPlayerReady,
//             'onStateChange' : onPlayerStateChange
//         }
//     });
// }

// // Append this state listener logic inside your existing music.js file

// function onPlayerReady(event) {
//     const startButton = document.getElementById('start-btn');
//     const overlay = document.getElementById('welcome-overlay');
//     const musicToggle = document.getElementById('music-toggle');

//     // Handle initial entrance click behavior
//     startButton.addEventListener('click', () => {
//         // If user unchecked it in the overlay settings before clicking enter
//         if (musicToggle.checked) {
//             player.playVideo();
//         }
        
//         overlay.style.opacity = '0';
//         setTimeout(() => overlay.style.display = 'none', 500);
//     });

//     // Monitor live configuration switches in the options tab dashboard
//     musicToggle.addEventListener('change', (e) => {
//         if (e.target.checked) {
//             // Unmute and verify the track is actively executing 
//             player.unmute();
//             player.playVideo(); 
//         } else {
//             // Mute instantly without breaking playlist position tracks
//             player.mute();
//         }
//     });
// }


// //  2. Fallback protection loop for short tracks or single-video loops
// function onPlayerStateChange(event) {
//     if (event.data === YT.PlayerState.ENDED) {
//         player.playVideo();
//     }
// }