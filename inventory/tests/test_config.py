from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from common.env import get_database_url


class ConfigTests(SimpleTestCase):
    @patch("common.env.load_project_env")
    @patch.dict("os.environ", {}, clear=True)
    def test_database_url_is_required(self, _mock_load_project_env):
        with self.assertRaises(ImproperlyConfigured):
            get_database_url()
