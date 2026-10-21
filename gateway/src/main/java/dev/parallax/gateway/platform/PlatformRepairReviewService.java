package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;
import java.util.UUID;
import java.util.List;

import com.fasterxml.jackson.databind.ObjectMapper;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.task.TaskState;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Authoritative repair review record. A platform approval binds the exact source and
 * patch bytes; an approval alone never claims that an isolated regression passed.
 */
@Service
public class PlatformRepairReviewService {
    public enum Status { AWAITING_APPROVAL, APPROVED, REJECTED, VERIFYING, PASSED, FAILED }
    public record ProposalRequest(String sourceCommitSha, String patchSha256, String patchContent, String testCommand) { }
    public record VerificationRequest(String verificationId, String approvalDigest, String resultSha256, boolean passed, String detail) { }
    public record Review(String id, String taskId, String projectId, String createdBy, String sourceCommitSha,
            String patchSha256, String patchContent, String testCommand, String approvalDigest, Status status,
            String approvedBy, Instant approvedAt, String verificationId, String verificationSha256,
            String verificationDetail, Instant createdAt, Instant updatedAt) { }

    private final JdbcTemplate jdbc;
    private final PlatformIdentityService identity;
    private final PlatformTaskService tasks;
    private final ObjectMapper mapper;

    public PlatformRepairReviewService(JdbcTemplate jdbc, PlatformIdentityService identity, PlatformTaskService tasks, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.identity = identity;
        this.tasks = tasks;
        this.mapper = mapper;
    }

    @Transactional
    public Review propose(String actor, String projectId, String taskId, ProposalRequest request) {
        identity.project(actor, projectId, ProjectRole.REVIEWER);
        tasks.get(actor, projectId, taskId);
        // Serialize duplicate proposals without catching a uniqueness error inside a
        // transaction (PostgreSQL marks such a transaction aborted).
        var task = tasks.current(taskId, true);
        if (task.state() != TaskState.SUCCEEDED) throw conflict("A repair requires a successful audit result");
        validateProposal(request, task.commitSha());
        String digest = approvalDigest(task, request.patchSha256(), request.testCommand());
        var existing = jdbc.query("SELECT * FROM platform_repair_review WHERE task_id=? AND approval_digest=? FOR UPDATE",
                (rs, n) -> review(rs), taskId, digest);
        if (!existing.isEmpty()) { requireIntegrity(existing.getFirst()); return existing.getFirst(); }
        String id = UUID.randomUUID().toString();
        Instant now = now();
        jdbc.update("INSERT INTO platform_repair_review (id,task_id,project_id,created_by,source_commit_sha,patch_sha256,patch_content,test_command,approval_digest,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,'AWAITING_APPROVAL',?,?)",
                    id, taskId, projectId, actor, task.commitSha(), request.patchSha256(), request.patchContent(), request.testCommand(), digest, Timestamp.from(now), Timestamp.from(now));
        identity.audit(actor, "REPAIR_PROPOSED", id);
        return get(actor, projectId, taskId, id);
    }

    @Transactional
    public Review approve(String actor, String projectId, String taskId, String reviewId, String approvalDigest) {
        identity.project(actor, projectId, ProjectRole.MAINTAINER);
        Review review = locked(projectId, taskId, reviewId);
        requireIntegrity(review);
        if (!MessageDigest.isEqual(review.approvalDigest().getBytes(StandardCharsets.US_ASCII), safeDigest(approvalDigest).getBytes(StandardCharsets.US_ASCII))) {
            throw conflict("Approval digest does not match the immutable proposal");
        }
        if (review.approvedBy() != null) return review;
        if (review.status() != Status.AWAITING_APPROVAL) throw conflict("Repair proposal is no longer awaiting approval");
        Instant now = now();
        jdbc.update("UPDATE platform_repair_review SET status='APPROVED',approved_by=?,approved_at=?,updated_at=? WHERE id=? AND status='AWAITING_APPROVAL'",
                actor, Timestamp.from(now), Timestamp.from(now), reviewId);
        identity.audit(actor, "REPAIR_APPROVED", reviewId);
        return get(actor, projectId, taskId, reviewId);
    }

    @Transactional
    public Review verify(String projectId, String taskId, String reviewId, VerificationRequest request) {
        if (request == null || request.verificationId() == null || !request.verificationId().matches("[A-Za-z0-9_.:/-]{1,120}")) throw ApiException.badRequest("Invalid verification id");
        if (request.resultSha256() == null || !request.resultSha256().matches("[0-9a-f]{64}")) throw ApiException.badRequest("Verification digest is required");
        if (request.detail() == null || request.detail().getBytes(StandardCharsets.UTF_8).length > 20000) throw ApiException.badRequest("Verification detail is missing or too large");
        Review review = locked(projectId, taskId, reviewId);
        requireIntegrity(review);
        if (!review.approvalDigest().equals(request.approvalDigest()) || !digest(request.detail()).equals(request.resultSha256())) throw conflict("Verification evidence digest or approval binding mismatch");
        validateEvidence(review, request);
        if (review.status() == Status.PASSED || review.status() == Status.FAILED) {
            if (request.verificationId().equals(review.verificationId()) && request.resultSha256().equals(review.verificationSha256())
                    && request.detail().equals(review.verificationDetail()) && request.passed() == (review.status() == Status.PASSED)) return review;
            throw conflict("Repair verification is already final");
        }
        if (review.status() != Status.APPROVED && review.status() != Status.VERIFYING) throw conflict("Repair must be approved before isolated verification");
        Instant now = now();
        jdbc.update("UPDATE platform_repair_review SET status=?,verification_id=?,verification_sha256=?,verification_detail=?,updated_at=? WHERE id=?",
                request.passed() ? Status.PASSED.name() : Status.FAILED.name(), request.verificationId(), request.resultSha256(), request.detail(), Timestamp.from(now), reviewId);
        identity.audit("platform-worker", request.passed() ? "REPAIR_VERIFIED" : "REPAIR_REGRESSION_FAILED", reviewId);
        return locked(projectId, taskId, reviewId);
    }

    public Review get(String actor, String projectId, String taskId, String reviewId) {
        identity.project(actor, projectId, ProjectRole.VIEWER);
        Review result = jdbc.query("SELECT * FROM platform_repair_review WHERE id=? AND task_id=? AND project_id=?", (rs, n) -> review(rs), reviewId, taskId, projectId)
                .stream().findFirst().orElseThrow(PlatformRepairReviewService::notFound);
        requireIntegrity(result);
        return result;
    }

    public CursorPage<Review> list(String actor, String projectId, String taskId, String after, int limit) {
        tasks.get(actor, projectId, taskId);
        CursorPage.validate(after, limit);
        var rows = jdbc.query("SELECT * FROM platform_repair_review WHERE project_id=? AND task_id=? AND id>? ORDER BY id LIMIT ?", (rs,n) -> review(rs), projectId, taskId, after, limit+1);
        rows.forEach(this::requireIntegrity);
        return CursorPage.of(rows, limit, Review::id);
    }

    private void requireIntegrity(Review review) {
        var task = tasks.current(review.taskId(), false);
        if (!task.projectId().equals(review.projectId()) || !task.commitSha().equals(review.sourceCommitSha())
                || !digest(review.patchContent()).equals(review.patchSha256())
                || !approvalDigest(task, review.patchSha256(), review.testCommand()).equals(review.approvalDigest())) throw conflict("Repair proposal integrity check failed");
        if (review.verificationDetail() != null && !digest(review.verificationDetail()).equals(review.verificationSha256())) throw conflict("Repair verification integrity check failed");
    }

    private String approvalDigest(PlatformTaskService.Task task, String patchSha256, String command) {
        if (task.resultSha256() == null) throw conflict("Repair requires a bound audit result");
        try { return digest(mapper.writeValueAsString(List.of("parallax-repair-v1", task.id(), task.commitSha(), task.resultSha256(), patchSha256, command))); }
        catch (com.fasterxml.jackson.core.JsonProcessingException ex) { throw new IllegalStateException(ex); }
    }

    private void validateEvidence(Review review, VerificationRequest request) {
        try {
            var evidence = mapper.readTree(request.detail());
            if (evidence == null || !evidence.isObject() || !review.id().equals(evidence.path("review_id").asText())
                    || !review.taskId().equals(evidence.path("task_id").asText())
                    || !review.sourceCommitSha().equals(evidence.path("source_commit_sha").asText())
                    || !review.patchSha256().equals(evidence.path("patch_sha256").asText())
                    || !review.testCommand().equals(evidence.path("test_command").asText())) throw conflict("Verification evidence differs from approved proposal");
            var baseline = evidence.path("baseline_exit_code");
            var regression = evidence.path("regression_exit_code");
            String marker = evidence.path("baseline_failure_contains").asText();
            boolean passed = baseline.isIntegralNumber() && baseline.canConvertToInt() && baseline.asInt() > 0 && baseline.asInt() <= 124
                    && regression.isIntegralNumber() && regression.canConvertToInt() && regression.asInt() == 0 && !marker.isBlank()
                    && evidence.path("baseline_output").asText().contains(marker)
                    && "regression_passed".equals(evidence.path("status").asText());
            if (request.passed() != passed) throw conflict("Verification outcome differs from execution evidence");
        } catch (com.fasterxml.jackson.core.JsonProcessingException ex) { throw ApiException.badRequest("Verification evidence must be valid JSON"); }
    }

    private Review locked(String projectId, String taskId, String reviewId) {
        return jdbc.query("SELECT * FROM platform_repair_review WHERE id=? AND task_id=? AND project_id=? FOR UPDATE", (rs, n) -> review(rs), reviewId, taskId, projectId)
                .stream().findFirst().orElseThrow(PlatformRepairReviewService::notFound);
    }

    private static void validateProposal(ProposalRequest request, String expectedSource) {
        if (request == null || request.sourceCommitSha() == null || !request.sourceCommitSha().equals(expectedSource)) throw conflict("Repair source must match the audited commit");
        if (request.patchSha256() == null || !request.patchSha256().matches("[0-9a-f]{64}")) throw ApiException.badRequest("Patch SHA-256 is required");
        if (request.patchContent() == null || request.patchContent().isEmpty() || request.patchContent().getBytes(StandardCharsets.UTF_8).length > 2_000_000) throw ApiException.badRequest("Patch is missing or too large");
        if (!digest(request.patchContent()).equals(request.patchSha256())) throw ApiException.badRequest("Patch digest does not match content");
        if (request.testCommand() == null || request.testCommand().isBlank() || request.testCommand().length() > 1000 || request.testCommand().chars().anyMatch(Character::isISOControl)) throw ApiException.badRequest("A single bounded test command is required");
    }

    private static String safeDigest(String value) { if (value == null || !value.matches("[0-9a-f]{64}")) throw ApiException.badRequest("Approval digest is required"); return value; }
    private static String digest(String value) { try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); } catch (Exception ex) { throw new IllegalStateException(ex); } }
    private static Instant now() { return Instant.now().truncatedTo(ChronoUnit.MICROS); }
    private static ApiException conflict(String message) { return new ApiException(HttpStatus.CONFLICT, message); }
    private static ApiException notFound() { return new ApiException(HttpStatus.NOT_FOUND, "Repair proposal not found"); }
    private static Review review(ResultSet rs) throws SQLException {
        Timestamp approved = rs.getTimestamp("approved_at"), created = rs.getTimestamp("created_at"), updated = rs.getTimestamp("updated_at");
        return new Review(rs.getString("id"), rs.getString("task_id"), rs.getString("project_id"), rs.getString("created_by"), rs.getString("source_commit_sha"), rs.getString("patch_sha256"), rs.getString("patch_content"), rs.getString("test_command"), rs.getString("approval_digest"), Status.valueOf(rs.getString("status")), rs.getString("approved_by"), approved == null ? null : approved.toInstant(), rs.getString("verification_id"), rs.getString("verification_sha256"), rs.getString("verification_detail"), created.toInstant(), updated.toInstant());
    }
}
