package dev.parallax.gateway.runs;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.persistence.criteria.Predicate;

/**
 * 运行历史的查询与过滤。
 *
 * 用 JPA Criteria 而不是一条带 `:param is null` 的 JPQL：
 * 后者在 Hibernate 6 上会因为无法推断 null 参数的类型而报错，
 * 而"可选过滤条件"恰恰是查询接口最常见的形状。
 */
@Service
public class RunQueryService {

    /** 单页上限。没有上限的话一次 `?size=100000` 就能把网关的内存打满。 */
    public static final int MAX_PAGE_SIZE = 200;

    private final AuditRunRepository runs;
    private final AuditEventRepository events;

    public RunQueryService(AuditRunRepository runs, AuditEventRepository events) {
        this.runs = runs;
        this.events = events;
    }

    public record Filter(String status, String credentialId, Instant since, Instant until) {
    }

    @Transactional(readOnly = true)
    public Page<AuditRun> search(Filter filter, int page, int size) {
        int safeSize = Math.min(Math.max(size, 1), MAX_PAGE_SIZE);
        PageRequest request = PageRequest.of(
                Math.max(page, 0), safeSize, Sort.by(Sort.Direction.DESC, "submittedAt"));
        return runs.findAll(toSpecification(filter), request);
    }

    private Specification<AuditRun> toSpecification(Filter filter) {
        return (root, query, builder) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (filter.status() != null && !filter.status().isBlank()) {
                predicates.add(builder.equal(root.get("status"), filter.status()));
            }
            if (filter.credentialId() != null && !filter.credentialId().isBlank()) {
                predicates.add(builder.equal(root.get("credentialId"), filter.credentialId()));
            }
            if (filter.since() != null) {
                predicates.add(builder.greaterThanOrEqualTo(root.get("submittedAt"), filter.since()));
            }
            if (filter.until() != null) {
                predicates.add(builder.lessThan(root.get("submittedAt"), filter.until()));
            }
            return predicates.isEmpty() ? null : builder.and(predicates.toArray(new Predicate[0]));
        };
    }

    @Transactional(readOnly = true)
    public Optional<AuditRun> findByRunId(String runId) {
        return runs.findByRunId(runId);
    }

    @Transactional(readOnly = true)
    public List<AuditEvent> eventsOf(String submissionId) {
        return events.findByRunIdOrderByAtAsc(submissionId);
    }
}
