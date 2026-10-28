from django.shortcuts import render

def home_view(request):
    # Extract just the 11-character video ID from the youtube link
    # Example link: https://youtube.com -> ID is 'dQw4w9WgXcQ'
    context = {
        'youtube_video_id' : 'MoPCsL5S6S4'
    }
    return render(request, 'index.html', context)