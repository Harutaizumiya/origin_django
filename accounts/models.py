from django.conf import settings
from django.db import models
from django.utils import timezone


class AuthToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "accounts_auth_tokens"
        indexes = [
            models.Index(fields=["user", "expires_at"], name="acct_auth_user_exp_idx"),
            models.Index(fields=["revoked_at"], name="acct_auth_revoked_idx"),
        ]

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()
