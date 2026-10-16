package dev.parallax.gateway.auth;

/** 认证主体。字段刻意只有 role：单租户部署不需要用户库，
 *  引入 User 实体会立刻把"薄网关"变成第二个业务后端。 */
public record AuthPrincipal(String subject, String role) {

    public static final String ROLE_ADMIN = "ADMIN";
    public static final String ROLE_VIEWER = "VIEWER";
}
