package dev.parallax.gateway.platform;

import dev.parallax.gateway.auth.AuthPrincipal;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
public class PlatformRepairReviewController {
    private final PlatformRepairReviewService reviews;
    public PlatformRepairReviewController(PlatformRepairReviewService reviews) { this.reviews = reviews; }

    @PostMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/repairs")
    public PlatformRepairReviewService.Review propose(@AuthenticationPrincipal AuthPrincipal principal, @PathVariable String projectId, @PathVariable String taskId, @Valid @RequestBody PlatformRepairReviewService.ProposalRequest request) {
        return reviews.propose(PlatformIdentityService.requireUser(principal), projectId, taskId, request);
    }

    @PostMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/repairs/{reviewId}/approve")
    public PlatformRepairReviewService.Review approve(@AuthenticationPrincipal AuthPrincipal principal, @PathVariable String projectId, @PathVariable String taskId, @PathVariable String reviewId, @RequestBody ApprovalRequest request) {
        return reviews.approve(PlatformIdentityService.requireUser(principal), projectId, taskId, reviewId, request == null ? null : request.approvalDigest());
    }

    @GetMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/repairs/{reviewId}")
    public PlatformRepairReviewService.Review get(@AuthenticationPrincipal AuthPrincipal principal, @PathVariable String projectId, @PathVariable String taskId, @PathVariable String reviewId) {
        return reviews.get(PlatformIdentityService.requireUser(principal), projectId, taskId, reviewId);
    }

    public record ApprovalRequest(String approvalDigest) { }

    @GetMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/repairs")
    public CursorPage<PlatformRepairReviewService.Review> list(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String taskId,
            @RequestParam(defaultValue="") String after, @RequestParam(defaultValue="20") int limit) {
        return reviews.list(PlatformIdentityService.requireUser(principal), projectId, taskId, after, limit);
    }
}
