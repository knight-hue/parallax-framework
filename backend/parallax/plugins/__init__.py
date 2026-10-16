"""内置插件。

插件是「证据来源 + 盲读方式」的组合。框架本身不含任何场景知识，
所有场景相关内容都收在这里。

已提供：
    code_audit   AI 生成代码的独立审查（主参考应用）
"""

from parallax.plugins.code_audit import CodeAuditReader, RepoAdapter

__all__ = ["CodeAuditReader", "RepoAdapter"]
