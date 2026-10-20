package dev.parallax.gateway.auth;

/**
 * 认证主体。
 *
 * 凭据类型：
 * - **JWT**（运营人员）：`credentialId`、`userId` 为 null，靠 `role` 授权；
 * - **API Key**（集成方）：`credentialId` 必填，配额与记账都按它归属。
 * - **用户 JWT**：`userId` 必填，成员关系实时查库，不能继承全局管理员角色。
 *
 * `subject` 用凭据的 `name` 而不是 id：日志里"ci-bot 超了额度"比一串 UUID 有用。
 */
public record AuthPrincipal(String subject, String role, String credentialId, String userId) {

    public static final String ROLE_ADMIN = "ADMIN";
    public static final String ROLE_VIEWER = "VIEWER";

    public AuthPrincipal(String subject, String role, String credentialId) {
        this(subject, role, credentialId, null);
    }

    /** JWT 主体（无配额归属）。 */
    public AuthPrincipal(String subject, String role) {
        this(subject, role, null);
    }

    public boolean hasCredential() {
        return credentialId != null && !credentialId.isBlank();
    }

    @Override
    public String toString() {
        // 刻意不输出 credentialId：它会被限流桶当成 key 的一部分、也会进日志，
        // 而它能唯一指向一把可用的 key。
        return subject + "(" + role + ")";
    }
}
