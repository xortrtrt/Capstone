ALTER TABLE orders
    ADD CONSTRAINT ck_orders_reseller_relationship
    CHECK (
        (order_type = 'reseller' AND reseller_id IS NOT NULL)
        OR (order_type = 'walk_in' AND reseller_id IS NULL)
    ),
    ADD CONSTRAINT ck_orders_fulfillment_timestamp
    CHECK (
        (status = 'fulfilled' AND fulfilled_at IS NOT NULL)
        OR (status <> 'fulfilled' AND fulfilled_at IS NULL)
    ),
    ADD CONSTRAINT ck_orders_review_metadata
    CHECK (
        status IN ('pending', 'cancelled')
        OR (approved_by_account_id IS NOT NULL AND approved_at IS NOT NULL)
    );
