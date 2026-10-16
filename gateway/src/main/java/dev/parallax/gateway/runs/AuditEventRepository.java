package dev.parallax.gateway.runs;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface AuditEventRepository extends JpaRepository<AuditEvent, Long> {

    List<AuditEvent> findByRunIdOrderByAtAsc(String runId);
}
