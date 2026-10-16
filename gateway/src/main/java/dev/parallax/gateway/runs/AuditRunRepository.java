package dev.parallax.gateway.runs;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AuditRunRepository extends JpaRepository<AuditRun, String>, JpaSpecificationExecutor<AuditRun> {

    Optional<AuditRun> findByRunId(String runId);

    /**
     * 配额的事实来源：某个凭据从某时刻起**提交**了多少次。
     *
     * 注意是 `submittedAt` 而不是完成时间——见 {@link AuditRun} 的说明。
     */
    long countByCredentialIdAndSubmittedAtGreaterThanEqual(String credentialId, Instant since);

    List<AuditRun> findByCredentialIdOrderBySubmittedAtDesc(String credentialId);
}
