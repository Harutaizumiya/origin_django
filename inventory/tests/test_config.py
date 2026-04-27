from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db.models import NOT_PROVIDED
from django.test import SimpleTestCase

from common.env import get_database_url
from inventory.models import Batch, Product


class ConfigTests(SimpleTestCase):
    @patch("common.env.load_project_env")
    @patch.dict("os.environ", {}, clear=True)
    def test_database_url_is_required(self, _mock_load_project_env):
        with self.assertRaises(ImproperlyConfigured):
            get_database_url()

    def test_database_timestamp_fields_use_database_defaults(self):
        self.assertIsNot(Product._meta.get_field("created_at").db_default, NOT_PROVIDED)
        self.assertIsNot(Product._meta.get_field("updated_at").db_default, NOT_PROVIDED)
        self.assertIsNot(Batch._meta.get_field("received_at").db_default, NOT_PROVIDED)
