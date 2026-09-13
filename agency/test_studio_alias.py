from django.conf import settings
from django.test import Client, TestCase


class StudioAliasTests(TestCase):
    def test_alias_uses_existing_portal_login_and_health(self):
        host = 'portalverdadeceara.studio.nabio.pro'
        response = self.client.get('/', HTTP_HOST=host, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Portal Verdade Ceará')
        self.assertEqual(self.client.get('/health/', HTTP_HOST=host, secure=True).status_code, 200)

    def test_alias_accepts_its_own_csrf_origin_without_disabling_protection(self):
        client = Client(enforce_csrf_checks=True)
        host = 'portalverdadeceara.studio.nabio.pro'
        client.get('/', HTTP_HOST=host, secure=True)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post('/', {'username':'missing-user', 'password':'invalid', 'csrfmiddlewaretoken':token}, HTTP_HOST=host, HTTP_ORIGIN='https://'+host, secure=True)
        self.assertNotEqual(response.status_code, 403)
        response = client.post('/', {'username':'missing-user','password':'invalid','csrfmiddlewaretoken':token}, HTTP_HOST=host, HTTP_ORIGIN='https://untrusted.example', secure=True)
        self.assertEqual(response.status_code, 403)
