package dev.parallax.gateway.identity;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface QuotaPolicyRepository extends JpaRepository<QuotaPolicy, Long> {

    Optional<QuotaPolicy> findByName(String name);

    List<QuotaPolicy> findAllByOrderByNameAsc();
}
