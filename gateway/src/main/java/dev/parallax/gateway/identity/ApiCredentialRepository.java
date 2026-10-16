package dev.parallax.gateway.identity;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ApiCredentialRepository extends JpaRepository<ApiCredential, String> {

    /** 按摘要查找。用摘要而不是明文比较，避免逐字节比较带来的时序信息。 */
    @EntityGraph(attributePaths = "quotaPolicy")
    Optional<ApiCredential> findByKeyHash(String keyHash);

    /**
     * 列表查询顺带取回配额策略。
     *
     * 不靠 `@ManyToOne(EAGER)` 解决：那会让配额热路径也带上一次多余关联，
     * 而这里的问题只是"实体在事务外被读到了策略字段"（`open-in-view=false`）。
     */
    @EntityGraph(attributePaths = "quotaPolicy")
    List<ApiCredential> findAllByOrderByCreatedAtDesc();

    Optional<ApiCredential> findByName(String name);

    /** 供配额校验与报表使用：策略字段会在事务外被读到，故一并取回。 */
    @EntityGraph(attributePaths = "quotaPolicy")
    Optional<ApiCredential> findWithQuotaById(String id);
}
