-- 必须在应用启动前执行：Seata 代理数据源时会先校验 undo_log 是否存在。
-- 用法：mysql -h 127.0.0.1 -P 3307 -u parallax -p seata_lab < labs/seata/sql/schema.sql
CREATE TABLE IF NOT EXISTS undo_log (
    branch_id BIGINT NOT NULL,
    xid VARCHAR(128) NOT NULL,
    context VARCHAR(128) NOT NULL,
    rollback_info LONGBLOB NOT NULL,
    log_status INT NOT NULL,
    log_created DATETIME(6) NOT NULL,
    log_modified DATETIME(6) NOT NULL,
    ext VARCHAR(100) DEFAULT NULL,
    UNIQUE KEY ux_undo_log (xid, branch_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS inventory (
    sku VARCHAR(64) PRIMARY KEY,
    available INT NOT NULL,
    frozen INT NOT NULL DEFAULT 0,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT ck_inventory_available CHECK (available >= 0),
    CONSTRAINT ck_inventory_frozen CHECK (frozen >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS shop_order (
    id BIGINT NOT NULL AUTO_INCREMENT,
    sku VARCHAR(64) NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_shop_order_sku (sku),
    CONSTRAINT ck_shop_order_quantity CHECK (quantity > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS tcc_reservation (
    id BIGINT NOT NULL AUTO_INCREMENT,
    xid VARCHAR(128) NOT NULL,
    sku VARCHAR(64) NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tcc_reservation_xid (xid, sku),
    CONSTRAINT ck_tcc_reservation_status CHECK (status IN ('TRY', 'CONFIRMED', 'CANCELLED'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

INSERT INTO inventory (sku, available, frozen, updated_at)
SELECT 'sku-1', 10, 0, CURRENT_TIMESTAMP(6)
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM inventory WHERE sku = 'sku-1');
