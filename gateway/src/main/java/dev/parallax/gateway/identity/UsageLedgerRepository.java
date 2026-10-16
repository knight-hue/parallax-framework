package dev.parallax.gateway.identity;

import java.time.Instant;
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface UsageLedgerRepository extends JpaRepository<UsageLedgerEntry, Long> {

    /** 用于回调幂等：同一次运行的完成回调可能被投递多次，只记第一笔。 */
    boolean existsByRunId(String runId);

    /** 区间内的运行次数。 */
    long countByCredentialIdAndOccurredAtGreaterThanEqual(String credentialId, Instant since);

    /** 区间内的 token 总量。用 coalesce 保证无记录时返回 0 而不是 null。 */
    @Query("""
            select coalesce(sum(u.totalTokens), 0)
            from UsageLedgerEntry u
            where u.credentialId = :credentialId and u.occurredAt >= :since
            """)
    long sumTokensSince(@Param("credentialId") String credentialId, @Param("since") Instant since);

    /** 管理端按凭据聚合的用量快照：返回 [credentialId, runs, tokens]。 */
    @Query("""
            select u.credentialId, count(u), coalesce(sum(u.totalTokens), 0)
            from UsageLedgerEntry u
            where u.occurredAt >= :since
            group by u.credentialId
            """)
    List<Object[]> aggregateSince(@Param("since") Instant since);

    List<UsageLedgerEntry> findByCredentialIdOrderByOccurredAtDesc(String credentialId);
}
