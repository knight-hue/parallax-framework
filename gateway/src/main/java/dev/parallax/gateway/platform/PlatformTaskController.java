package dev.parallax.gateway.platform;

import dev.parallax.gateway.auth.AuthPrincipal;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
public class PlatformTaskController {
    private final PlatformTaskService tasks;
    public PlatformTaskController(PlatformTaskService tasks) { this.tasks=tasks; }
    public record BudgetRequest(long tokenLimit) { }

    @PutMapping("/api/v1/platform/budgets/{organizationId}")
    @PreAuthorize("hasRole('ADMIN')")
    public PlatformTaskService.Budget configure(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String organizationId,@RequestBody BudgetRequest request) {
        return tasks.configureBudget(principal.subject(),organizationId,request.tokenLimit());
    }
    @GetMapping("/api/v1/platform/organizations/{organizationId}/budget")
    public PlatformTaskService.Budget budget(@AuthenticationPrincipal AuthPrincipal principal,@PathVariable String organizationId) {
        return tasks.budget(PlatformIdentityService.requireUser(principal),organizationId);
    }
    @GetMapping("/api/v1/platform/budgets/{organizationId}/reconciliation")
    @PreAuthorize("hasRole('ADMIN')")
    public PlatformTaskService.Reconciliation reconcile(@PathVariable String organizationId) {
        return tasks.reconcile(organizationId);
    }
    @PostMapping("/api/v1/platform/projects/{projectId}/tasks")
    public PlatformTaskService.Task submit(@AuthenticationPrincipal AuthPrincipal principal,@PathVariable String projectId,
            @RequestHeader(value="Idempotency-Key",required=false) String key,@RequestBody PlatformTaskService.Submission request) {
        return tasks.submit(PlatformIdentityService.requireUser(principal),projectId,key,request);
    }
    @GetMapping("/api/v1/platform/projects/{projectId}/tasks")
    public CursorPage<PlatformTaskService.Task> list(@AuthenticationPrincipal AuthPrincipal principal,@PathVariable String projectId,
            @RequestParam(defaultValue="") String after,@RequestParam(defaultValue="50") int limit) {
        return tasks.tasks(PlatformIdentityService.requireUser(principal),projectId,after,limit);
    }
    @GetMapping("/api/v1/platform/projects/{projectId}/tasks/{id}")
    public PlatformTaskService.Task get(@AuthenticationPrincipal AuthPrincipal principal,@PathVariable String projectId,@PathVariable String id) {
        return tasks.get(PlatformIdentityService.requireUser(principal),projectId,id);
    }
    @PostMapping("/api/v1/platform/projects/{projectId}/tasks/{id}/cancel")
    public PlatformTaskService.Task cancel(@AuthenticationPrincipal AuthPrincipal principal,@PathVariable String projectId,@PathVariable String id) {
        return tasks.cancel(PlatformIdentityService.requireUser(principal),projectId,id);
    }
}
