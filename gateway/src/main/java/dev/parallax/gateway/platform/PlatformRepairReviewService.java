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

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.task.TaskState;
import org.springframework.dao.DuplicateKeyException;
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
    public record VerificationRequest(String verificationId, String resultSha256, boolean passed, String detail) { }
    public record Review(String id, String taskId, String projectId, String createdBy, String sourceCommitSha,
            String patchSha256, String patchContent, String testCommand, String approvalDigest, Status status,
            String approvedBy, Instant approvedAt, String verificationId, String verificationSha256,
            String verificationDetail, Instant createdAt, Instant updatedAt) { }

    private final JdbcTemplate jdbc;
    private final PlatformIdentityService identity;
    private final PlatformTaskService tasks;

    public PlatformRepairReviewService(JdbcTemplate jdbc, PlatformIdentityService identity, PlatformTaskService tasks) {
        this.jdbc = jdbc;
        this.identity = identity;
        this.tasks = tasks;
    }

    @Transactional
    public Review propose(String actor, String projectId, String taskId, ProposalRequest request) {
        identity.project(actor, projectId, ProjectRole.REVIEWER);
        var task = tasks.get(actor, projectId, taskId);
        if (task.state() != TaskState.SUCCEEDED) throw conflict("A repair requires a successful audit result");
        validateProposal(request, task.commitSha());
        String digest = digest(task.commitSha() + "\n" + request.patchSha256() + "\n" + request.patchContent() + "\n" + request.testCommand());
        var existing = jdbc.query("SELECT * FROM platform_repair_review WHERE task_id=? AND approval_digest=?",
                (rs, n) -> review(rs), taskId, digest);
        if (!existing.isEmpty()) return existing.getFirst();
        String id = UUID.randomUUID().toString();
        Instant now = now();
        try {
            jdbc.update("INSERT INTO platform_repair_review (id,task_id,project_id,created_by,source_commit_sha,patch_sha256,patch_content,test_command,approval_digest,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,'AWAITING_APPROVAL',?,?)",
                    id, taskId, projectId, actor, task.commitSha(), request.patchSha256(), request.patchContent(), request.testCommand(), digest, Timestamp.from(now), Timestamp.from(now));
        } catch (DuplicateKeyException ex) {
            return jdbc.query("SELECT * FROM platform_repair_review WHERE task_id=? AND approval_digest=?", (rs, n) -> review(rs), taskId, digest).getFirst();
        }
        identity.audit(actor, "REPAIR_PROPOSED", id);
        return get(actor, projectId, taskId, id);
    }

    @Transactional
    public Review approve(String actor, String projectId, String taskId, String reviewId, String approvalDigest) {
        identity.project(actor, projectId, ProjectRole.MAINTAINER);
        Review review = locked(projectId, taskId, reviewId);
        if (!MessageDigest.isEqual(review.approvalDigest().getBytes(StandardCharsets.US_ASCII), safeDigest(approvalDigest).getBytes(StandardCharsets.US_ASCII))) {
            throw conflict("Approval digest does not match the immutable proposal");
        }
        if (review.status() == Status.APPROVED || review.status() == Status.VERIFYING || review.status() == Status.PASSED) return review;
        if (review.status() != Status.AWAITING_APPROVAL) throw conflict("Repair proposal is no longer awaiting approval");
        Instant now = now();
        jdbc.update("UPDATE platform_repair_review SET status='APPROVED',approved_by=?,approved_at=?,updated_at=? WHERE id=? AND status='AWAITING_APPROVAL'",
                actor, Timestamp.from(now), Timestamp.from(now), reviewId);
        identity.audit(actor, "REPAIR_APPROVED", reviewId);
        return get(actor, projectId, taskId, reviewId);
    }

    @Transactional
    public Review verify(String actor, String projectId, String taskId, String reviewId, VerificationRequest request) {
        identity.project(actor, projectId, ProjectRole.MAINTAINER);
        if (request == null || request.verificationId() == null || !request.verificationId().matches("[A-Za-z0-9_.:/-]{1,120}")) throw ApiException.badRequest("Invalid verification id");
        if (request.resultSha256() == null || !request.resultSha256().matches("[0-9a-f]{64}")) throw ApiException.badRequest("Verification digest is required");
        if (request.detail() == null || request.detail().length() > 20000) throw ApiException.badRequest("Verification detail is missing or too large");
        Review review = locked(projectId, taskId, reviewId);
        if (review.status() == Status.PASSED || review.status() == Status.FAILED) {
            if (request.verificationId().equals(review.verificationId()) && request.resultSha256().equals(review.verificationSha256())) return review;
            throw conflict("Repair verification is already final");
        }
        if (review.status() != Status.APPROVED && review.status() != Status.VERIFYING) throw conflict("Repair must be approved before isolated verification");
        Instant now = now();
        jdbc.update("UPDATE platform_repair_review SET status=?,verification_id=?,verification_sha256=?,verification_detail=?,updated_at=? WHERE id=?",
                request.passed() ? Status.PASSED.name() : Status.FAILED.name(), request.verificationId(), request.resultSha256(), request.detail(), Timestamp.from(now), reviewId);
        identity.audit(actor, request.passed() ? "REPAIR_VERIFIED" : "REPAIR_REGRESSION_FAILED", reviewId);
        return get(actor, projectId, taskId, reviewId);
    }

    public Review get(String actor, String projectId, String taskId, String reviewId) {
        identity.project(actor, projectId, ProjectRole.VIEWER);
        return jdbc.query("SELECT * FROM platform_repair_review WHERE id=? AND task_id=? AND project_id=?", (rs, n) -> review(rs), reviewId, taskId, projectId)
                .stream().findFirst().orElseThrow(PlatformRepairReviewService::notFound);
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
        if (request.testCommand() == null || request.testCommand().isBlank() || request.testCommand().length() > 1000 || request.testCommand().contains("\n")) throw ApiException.badRequest("A single bounded test command is required");
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
