"""P-052 S 组：鉴权契约（S1-S2）。"""

from __future__ import annotations

from core.interfaces import AuthConfig


def test_s1_auth_config_defaults():
    """S1：默认本机绑定 + 默认 local 模式 + 开启 401/403。"""
    config = AuthConfig()
    assert config.mode == "local"
    assert config.bind_host == "127.0.0.1"
    assert config.require_tls is False
    assert config.allowed_origins == ()
    assert config.enable_401_403 is True


def test_s2_auth_config_no_secret_inline():
    """S2：密钥只经环境变量名注入，配置对象内不含密钥明文。"""
    config = AuthConfig()
    assert config.api_key_env == "FT_API_KEY"
    assert not any("secret" in field for field in config.__dataclass_fields__)
    assert not any("password" in field for field in config.__dataclass_fields__)
