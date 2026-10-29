from django.shortcuts import render

def home_view(request):
    context = {
        'youtube_video_id' : 'MoPCsL5S6S4'
    }
    # Make sure you are using 'render', NOT 'HttpResponse'
    return render(request, 'index.html', context)