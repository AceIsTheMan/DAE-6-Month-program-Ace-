from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from mail.models import Conversation, ConversationParticipant, Message, ModerationAction, Report, Warning


class AdminPermissionOverhaulTest(TestCase):
    def setUp(self):
        self.director = CustomUser.objects.create_user(username='director1', password='pw', role=CustomUser.ROLE_DIRECTOR)
        self.admin1 = CustomUser.objects.create_user(username='admin1', password='pw', role=CustomUser.ROLE_ADMIN)
        self.admin2 = CustomUser.objects.create_user(username='admin2', password='pw', role=CustomUser.ROLE_ADMIN)
        self.alice = CustomUser.objects.create_user(username='alice', password='pw')

    def test_admin_cannot_moderate_admin(self):
        self.client.login(username='admin1', password='pw')
        r = self.client.post(reverse('mail_moderation_new', args=['admin2']), {
            'kind': 'mute', 'duration_amount': 1, 'duration_unit': 'weeks', 'reason': 'testing',
        })
        self.assertEqual(r.status_code, 403)
        self.assertEqual(ModerationAction.objects.count(), 0)

    def test_director_can_moderate_admin(self):
        self.client.login(username='director1', password='pw')
        r = self.client.post(reverse('mail_moderation_new', args=['admin2']), {
            'kind': 'mute', 'duration_amount': 1, 'duration_unit': 'weeks', 'reason': 'testing',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ModerationAction.objects.filter(target=self.admin2).count(), 1)

    def test_admin_report_resolve_is_a_request_not_final(self):
        report = Report.objects.create(reporter=self.alice, reported_user=self.alice, category=Report.BULLYING, reason='x')
        self.client.login(username='admin1', password='pw')
        r = self.client.post(reverse('mail_report_resolve', args=[report.id]), {'status': 'resolved'})
        self.assertEqual(r.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.OPEN)
        self.assertEqual(report.admin_requested_status, Report.RESOLVED)
        self.assertEqual(report.admin_requested_by, self.admin1)

    def test_director_report_resolve_is_final(self):
        report = Report.objects.create(reporter=self.alice, reported_user=self.alice, category=Report.BULLYING, reason='x')
        self.client.login(username='director1', password='pw')
        r = self.client.post(reverse('mail_report_resolve', args=[report.id]), {'status': 'resolved'})
        self.assertEqual(r.status_code, 204)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.RESOLVED)

    def test_report_warn_creates_masked_directive(self):
        report = Report.objects.create(reporter=self.admin1, reported_user=self.alice, category=Report.BULLYING, reason='x')
        self.client.login(username='admin1', password='pw')
        r = self.client.post(reverse('mail_report_warn', args=[report.id]), {'message': 'watch it'})
        self.assertEqual(r.status_code, 200)
        w = Warning.objects.get(target=self.alice)
        self.assertEqual(w.source, Warning.REPORT)
        self.assertEqual(w.issued_by, self.admin1)
        directive = w.directive_message
        self.assertEqual(directive.conversation.category, Conversation.DIRECTIVE)
        # Alice (not director) sees it masked; Director sees the real sender.
        from mail.templatetags.mail_extras import warn_sender_display
        self.assertEqual(warn_sender_display(directive, self.alice), 'Moderation Team')
        self.assertEqual(warn_sender_display(directive, self.director), 'admin1')

    def test_message_soft_delete_hides_from_thread_but_row_survives(self):
        convo = Conversation.objects.create(category=Conversation.SOCIAL, created_by=self.alice)
        ConversationParticipant.objects.create(conversation=convo, user=self.alice)
        ConversationParticipant.objects.create(conversation=convo, user=self.admin1)
        msg = Message.objects.create(conversation=convo, sender=self.alice, body='hello')

        self.client.login(username='alice', password='pw')
        r = self.client.post(reverse('mail_message_delete', args=[msg.id]))
        self.assertEqual(r.status_code, 204)
        msg.refresh_from_db()
        self.assertTrue(msg.is_deleted)
        self.assertEqual(Message.objects.count(), 1)  # still exists, just flagged

        thread = self.client.get(reverse('mail_social_thread', args=[convo.id]))
        self.assertNotContains(thread, 'hello')

    def test_directive_message_cannot_be_deleted(self):
        convo = Conversation.objects.create(category=Conversation.DIRECTIVE, created_by=self.director)
        ConversationParticipant.objects.create(conversation=convo, user=self.alice)
        msg = Message.objects.create(conversation=convo, sender=self.director, body='directive body')
        self.client.login(username='director1', password='pw')
        r = self.client.post(reverse('mail_message_delete', args=[msg.id]))
        self.assertEqual(r.status_code, 403)
        msg.refresh_from_db()
        self.assertFalse(msg.is_deleted)

    def test_comment_delete_now_allows_admin(self):
        from forum.models import Comment, Post
        post = Post.objects.create(author=self.director, body='post')
        comment = Comment.objects.create(post=post, author=self.alice, body='a comment')
        self.client.login(username='admin1', password='pw')
        r = self.client.post(reverse('forum_delete_comment', args=[comment.id]))
        self.assertEqual(r.status_code, 204)
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)
