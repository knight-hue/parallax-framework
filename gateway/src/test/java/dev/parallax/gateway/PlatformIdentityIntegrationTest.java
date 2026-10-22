package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import java.util.UUID;

import dev.parallax.gateway.auth.JwtService;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "parallax.gateway.require-auth=true", "parallax.ratelimit.enabled=false",
        "parallax.jwt.secret=0123456789abcdef0123456789abcdef", "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
class PlatformIdentityIntegrationTest {
    @Autowired TestRestTemplate rest;
    @Autowired JwtService jwt;
    @Autowired JdbcTemplate jdbc;

    private static final String PASSWORD = "correct-password-123";

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() { };

    private ResponseEntity<Map<String, Object>> call(HttpMethod method, String path, String token, Object body) {
        var headers = new HttpHeaders();
        if (token != null) headers.setBearerAuth(token);
        return rest.exchange(path, method, new HttpEntity<>(body, headers), MAP_TYPE);
    }

    private String admin() { return jwt.issueAccessToken("operator", "ADMIN"); }

    private Map<String, Object> user() {
        String name = "user-" + UUID.randomUUID();
        var response = call(HttpMethod.POST, "/api/v1/platform/users", admin(),
                Map.of("username", name, "password", PASSWORD));
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return response.getBody();
    }

    private String token(Map<String, Object> user) {
        var response = call(HttpMethod.POST, "/api/v1/auth/login", null,
                Map.of("username", user.get("username"), "password", PASSWORD));
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return (String) response.getBody().get("accessToken");
    }

    private String organization(String token) {
        var response = call(HttpMethod.POST, "/api/v1/platform/organizations", token, Map.of("name", "Team"));
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return (String) response.getBody().get("id");
    }

    @Test
    void projectResourcesAreIsolatedAndMembershipRevocationIsLive() {
        Map<String, Object> owner = user(); Map<String, Object> outsider = user();
        String ownerToken = token(owner), outsiderToken = token(outsider);
        String org = organization(ownerToken);
        var project = call(HttpMethod.POST, "/api/v1/platform/organizations/" + org + "/projects",
                ownerToken, Map.of("name", "payments"));
        assertThat(project.getStatusCode()).isEqualTo(HttpStatus.OK);
        String projectPath = "/api/v1/platform/projects/" + project.getBody().get("id");
        assertThat(call(HttpMethod.GET, projectPath, outsiderToken, null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(call(HttpMethod.GET, "/api/v1/audits/legacy-run/result", outsiderToken, null).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(call(HttpMethod.POST, "/api/v1/platform/organizations/" + org + "/members", ownerToken,
                Map.of("userId", outsider.get("id"), "role", "VIEWER")).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(call(HttpMethod.GET, projectPath, outsiderToken, null).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(call(HttpMethod.POST, "/api/v1/platform/organizations/" + org + "/projects", outsiderToken,
                Map.of("name", "forbidden")).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(call(HttpMethod.DELETE, "/api/v1/platform/organizations/" + org + "/members/" + outsider.get("id"),
                ownerToken, null).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(call(HttpMethod.GET, projectPath, outsiderToken, null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void disabledUsersCannotReuseExistingTokensOrLogin() {
        Map<String, Object> user = user(); String token = token(user);
        assertThat(call(HttpMethod.GET, "/api/v1/platform/me", token, null).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(call(HttpMethod.DELETE, "/api/v1/platform/users/" + user.get("id"), admin(), null).getStatusCode())
                .isEqualTo(HttpStatus.OK);
        assertThat(call(HttpMethod.GET, "/api/v1/platform/me", token, null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(call(HttpMethod.POST, "/api/v1/auth/login", null,
                Map.of("username", user.get("username"), "password", PASSWORD)).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void passwordHashesAndCredentialsAreNotExposed() {
        Map<String, Object> user = user();
        assertThat(user).doesNotContainKeys("password", "password_hash", "passwordHash");
        String stored = jdbc.queryForObject("SELECT password_hash FROM platform_user WHERE id = ?", String.class, user.get("id"));
        assertThat(stored).startsWith("$2a$12$").isNotEqualTo(PASSWORD);
        assertThat(new dev.parallax.gateway.platform.PlatformController.UserRequest("user", PASSWORD).toString())
                .doesNotContain(PASSWORD);
        assertThat(call(HttpMethod.POST, "/api/v1/auth/login", null,
                Map.of("username", user.get("username"), "password", "wrong-password")).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void normalUserCannotProvisionUsersAndOwnerCannotRemoveItself() {
        Map<String, Object> user = user(); String token = token(user); String org = organization(token);
        assertThat(call(HttpMethod.POST, "/api/v1/platform/users", token,
                Map.of("username", "unauthorized", "password", PASSWORD)).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(call(HttpMethod.DELETE, "/api/v1/platform/organizations/" + org + "/members/" + user.get("id"), token, null)
                .getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(call(HttpMethod.GET, "/api/v1/platform/me", admin(), null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void normalizedDuplicatesAreConflictsAndDoNotCreateAuditEntries() {
        Map<String, Object> user = user();
        var response = call(HttpMethod.POST, "/api/v1/platform/users", admin(),
                Map.of("username", user.get("username").toString().toUpperCase(java.util.Locale.ROOT), "password", PASSWORD));
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_access_audit WHERE resource_id = ? AND action = 'USER_PROVISIONED'",
                Integer.class, user.get("id"))).isEqualTo(1);
    }
}
