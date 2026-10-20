package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.common.ApiException;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PlatformIdentityService {
    public record UserView(String id, String username, boolean disabled) { }
    public record Organization(String id, String name, String role) { }
    public record Project(String id, String organizationId, String name) { }
    public record Member(String userId, String username, String role) { }

    private final JdbcTemplate jdbc;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(12);
    private final String dummyHash = encoder.encode(UUID.randomUUID().toString());

    public PlatformIdentityService(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @Transactional
    public UserView provision(String actor, String username, String password) {
        String normalized = normalize(username);
        validatePassword(password);
        String id = UUID.randomUUID().toString();
        try {
            jdbc.update("INSERT INTO platform_user (id, username, password_hash, disabled, created_at) VALUES (?, ?, ?, ?, ?)",
                    id, normalized, encoder.encode(password), false, Timestamp.from(Instant.now()));
        } catch (DuplicateKeyException ex) {
            throw new ApiException(HttpStatus.CONFLICT, "Username already exists");
        }
        audit(actor, "USER_PROVISIONED", id);
        return new UserView(id, normalized, false);
    }

    public UserView login(String username, String password) {
        String normalized = username == null ? "" : username.strip().toLowerCase(Locale.ROOT);
        var users = jdbc.query("SELECT id, username, password_hash, disabled FROM platform_user WHERE username = ?",
                (rs, n) -> new Object[]{rs.getString(1), rs.getString(2), rs.getString(3), rs.getBoolean(4)}, normalized);
        Object[] user = users.isEmpty() ? null : users.getFirst();
        String hash = user == null ? dummyHash : (String) user[2];
        // Bound BCrypt input and keep missing/disabled/wrong-password responses indistinguishable.
        String candidate = password == null ? "" : password;
        boolean sized = candidate.getBytes(StandardCharsets.UTF_8).length <= 72;
        boolean matches = encoder.matches(sized ? candidate : "", hash);
        if (!sized || !matches || user == null || (boolean) user[3]) {
            throw ApiException.unauthorized("Invalid username or password");
        }
        return new UserView((String) user[0], (String) user[1], false);
    }

    public UserView activeUser(String id) {
        return jdbc.query("SELECT id, username, disabled FROM platform_user WHERE id = ? AND disabled = FALSE",
                (rs, n) -> new UserView(rs.getString(1), rs.getString(2), rs.getBoolean(3)), id)
                .stream().findFirst().orElseThrow(() -> ApiException.unauthorized("User unavailable"));
    }

    @Transactional
    public void disable(String actor, String id) {
        if (jdbc.update("UPDATE platform_user SET disabled = TRUE WHERE id = ?", id) == 0) throw notFound();
        audit(actor, "USER_DISABLED", id);
    }

    @Transactional
    public Organization createOrganization(String userId, String name) {
        activeUser(userId);
        validateName(name);
        String id = UUID.randomUUID().toString();
        jdbc.update("INSERT INTO platform_organization (id, name, created_at) VALUES (?, ?, ?)",
                id, name.strip(), Timestamp.from(Instant.now()));
        jdbc.update("INSERT INTO platform_membership (organization_id, user_id, role) VALUES (?, ?, 'OWNER')", id, userId);
        audit(userId, "ORGANIZATION_CREATED", id);
        return new Organization(id, name.strip(), "OWNER");
    }

    public List<Organization> organizations(String userId) {
        return jdbc.query("SELECT o.id, o.name, m.role FROM platform_organization o JOIN platform_membership m ON m.organization_id = o.id WHERE m.user_id = ? ORDER BY o.id",
                (rs, n) -> new Organization(rs.getString(1), rs.getString(2), rs.getString(3)), userId);
    }

    public ProjectRole requireRole(String userId, String organizationId, ProjectRole minimum) {
        var roles = jdbc.query("SELECT role FROM platform_membership WHERE organization_id = ? AND user_id = ?",
                (rs, n) -> ProjectRole.valueOf(rs.getString(1)), organizationId, userId);
        if (roles.isEmpty()) throw notFound();
        if (!roles.getFirst().permits(minimum)) throw new ApiException(HttpStatus.FORBIDDEN, "Insufficient project role");
        return roles.getFirst();
    }

    @Transactional
    public void addMember(String actor, String organizationId, String userId, ProjectRole role) {
        requireRole(actor, organizationId, ProjectRole.OWNER);
        if (role == null || role == ProjectRole.OWNER) throw ApiException.badRequest("Ownership transfer is not supported");
        activeUser(userId);
        try {
            jdbc.update("INSERT INTO platform_membership (organization_id, user_id, role) VALUES (?, ?, ?)",
                    organizationId, userId, role.name());
        } catch (DuplicateKeyException ex) {
            throw new ApiException(HttpStatus.CONFLICT, "User is already a member");
        }
        audit(actor, "MEMBER_ADDED", organizationId);
    }

    @Transactional
    public void removeMember(String actor, String organizationId, String userId) {
        requireRole(actor, organizationId, ProjectRole.OWNER);
        int changed = jdbc.update("DELETE FROM platform_membership WHERE organization_id = ? AND user_id = ? AND role <> 'OWNER'",
                organizationId, userId);
        if (changed == 0) throw ApiException.badRequest("Member unavailable or protected owner");
        audit(actor, "MEMBER_REMOVED", organizationId);
    }

    public List<Member> members(String userId, String organizationId) {
        requireRole(userId, organizationId, ProjectRole.OWNER);
        return jdbc.query("SELECT u.id, u.username, m.role FROM platform_membership m JOIN platform_user u ON u.id = m.user_id WHERE m.organization_id = ? ORDER BY u.id",
                (rs, n) -> new Member(rs.getString(1), rs.getString(2), rs.getString(3)), organizationId);
    }

    @Transactional
    public Project createProject(String userId, String organizationId, String name) {
        requireRole(userId, organizationId, ProjectRole.MAINTAINER);
        validateName(name);
        String id = UUID.randomUUID().toString();
        try {
            jdbc.update("INSERT INTO platform_project (id, organization_id, name, created_at) VALUES (?, ?, ?, ?)",
                    id, organizationId, name.strip(), Timestamp.from(Instant.now()));
        } catch (DuplicateKeyException ex) {
            throw new ApiException(HttpStatus.CONFLICT, "Project name already exists in this organization");
        }
        audit(userId, "PROJECT_CREATED", id);
        return new Project(id, organizationId, name.strip());
    }

    public List<Project> projects(String userId, String organizationId) {
        requireRole(userId, organizationId, ProjectRole.VIEWER);
        return jdbc.query("SELECT id, organization_id, name FROM platform_project WHERE organization_id = ? ORDER BY id",
                (rs, n) -> new Project(rs.getString(1), rs.getString(2), rs.getString(3)), organizationId);
    }

    public Project project(String userId, String projectId, ProjectRole minimum) {
        var projects = jdbc.query("SELECT id, organization_id, name FROM platform_project WHERE id = ?",
                (rs, n) -> new Project(rs.getString(1), rs.getString(2), rs.getString(3)), projectId);
        if (projects.isEmpty()) throw notFound();
        Project project = projects.getFirst();
        requireRole(userId, project.organizationId(), minimum);
        return project;
    }

    public static String requireUser(AuthPrincipal principal) {
        if (principal == null || principal.userId() == null || principal.hasCredential()) {
            throw ApiException.unauthorized("A platform user token is required");
        }
        return principal.userId();
    }

    private void audit(String actor, String action, String resource) {
        jdbc.update("INSERT INTO platform_access_audit (id, actor, action, resource_id, at) VALUES (?, ?, ?, ?, ?)",
                UUID.randomUUID().toString(), actor, action, resource, Timestamp.from(Instant.now()));
    }

    private static String normalize(String value) {
        if (value == null || !value.matches("[A-Za-z0-9_.-]{3,64}")) throw ApiException.badRequest("Invalid username");
        return value.toLowerCase(Locale.ROOT);
    }

    private static void validatePassword(String value) {
        if (value == null || value.length() < 12 || value.getBytes(StandardCharsets.UTF_8).length > 72) {
            throw ApiException.badRequest("Password must have at least 12 characters and at most 72 UTF-8 bytes");
        }
    }

    private static void validateName(String value) {
        if (value == null || value.isBlank() || value.length() > 120) throw ApiException.badRequest("Invalid name");
    }

    private static ApiException notFound() { return new ApiException(HttpStatus.NOT_FOUND, "Resource not found"); }
}
