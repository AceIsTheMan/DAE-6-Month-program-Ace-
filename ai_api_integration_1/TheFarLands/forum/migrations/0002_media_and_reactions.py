import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_video_url_into_link(apps, schema_editor):
    """Removing the standalone "video link" field (see forum/models.py) -
    fold any existing video_url into link_url first so nothing already
    posted just vanishes. Only applies where link_url is still blank;
    the rare post that already used both fields keeps its link as-is and
    drops the old video_url (no safe way to merge two URLs into one)."""
    Post = apps.get_model('forum', 'Post')
    for post in Post.objects.exclude(video_url='').filter(link_url=''):
        post.link_url = post.video_url
        if not post.link_label:
            post.link_label = 'Video'
        post.save(update_fields=['link_url', 'link_label'])


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(move_video_url_into_link, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='post',
            name='image',
        ),
        migrations.RemoveField(
            model_name='post',
            name='video_url',
        ),
        migrations.AddField(
            model_name='post',
            name='media',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='forum_posts/media/',
                validators=[django.core.validators.FileExtensionValidator(
                    allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'webm', 'mov', 'ogg']
                )],
            ),
        ),
        migrations.CreateModel(
            name='PostReaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(choices=[('like', 'Like'), ('dislike', 'Dislike')], max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='forum.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forum_reactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('post', 'user'), name='one_reaction_per_user_per_post')],
            },
        ),
    ]
