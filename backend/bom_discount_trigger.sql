-- Assumption: the screenshot's table is public.bom_and_costing.
-- Change the schema below if necessary.
-- discount_bath now stores the NET UNIT PRICE after the percentage discount.
-- net_unit_price = unit_price * (1 - discount_pct / 100).
-- total_price = discount_bath * quantity.
-- Use decimal-capable columns (prefer NUMERIC) to retain cents.
-- Optional conversion; check dependencies and the required maximum first:
-- ALTER TABLE public.bom_and_costing
--   ALTER COLUMN unit_price TYPE NUMERIC(18,2) USING unit_price::NUMERIC(18,2),
--   ALTER COLUMN discount_bath TYPE NUMERIC(18,2) USING discount_bath::NUMERIC(18,2),
--   ALTER COLUMN discount_pct TYPE NUMERIC(7,2) USING discount_pct::NUMERIC(7,2),
--   ALTER COLUMN total_price TYPE NUMERIC(18,2) USING total_price::NUMERIC(18,2);

BEGIN;

CREATE OR REPLACE FUNCTION pjtrk.fn_bom_discount_total()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $function$
DECLARE
    v_source TEXT := 'keep';
    v_price NUMERIC := NEW.unit_price::NUMERIC;
    v_net NUMERIC;
    v_pct NUMERIC;
BEGIN
    -- INSERT has no OLD row. A nonzero net price takes priority;
    -- otherwise a supplied percentage takes priority over a default net 0.
    -- To insert a free item with defaults present, supply discount_pct = 100.
    IF TG_OP = 'INSERT' THEN
        IF COALESCE(NEW.discount_bath::NUMERIC, 0) <> 0 THEN
            v_source := 'net';
        ELSIF NEW.discount_pct IS NOT NULL THEN
            v_source := 'pct';
        ELSIF NEW.discount_bath IS NOT NULL THEN
            v_source := 'net';
        ELSE
            v_source := 'pct';
        END IF;
    ELSE
        -- Compare values, including NULL transitions.
        -- If both actually change, the net price takes priority.
        IF NEW.discount_bath IS DISTINCT FROM OLD.discount_bath THEN
            v_source := 'net';
        ELSIF NEW.discount_pct IS DISTINCT FROM OLD.discount_pct THEN
            v_source := 'pct';
        ELSIF NEW.unit_price IS DISTINCT FROM OLD.unit_price
           OR NEW.discount_bath IS NULL OR NEW.discount_pct IS NULL
           OR (NEW.discount_bath = 0 AND NEW.discount_pct <> 100) THEN
            IF NEW.discount_pct IS NOT NULL THEN
                v_source := 'pct';
            ELSE
                v_source := 'net';
            END IF;
        END IF;
    END IF;

    IF v_source <> 'keep' AND v_price IS NULL THEN
        RAISE EXCEPTION 'unit_price is required to calculate discounts';
    END IF;

    IF v_source = 'net' THEN
        -- Clearing the net price means no discount, not a free item.
        v_net := ROUND(COALESCE(NEW.discount_bath::NUMERIC, v_price), 2);
        IF v_price = 0 THEN
            IF v_net <> 0 THEN
                RAISE EXCEPTION
                    'A nonzero net unit price cannot be converted to a percentage when unit_price = 0';
            END IF;
            v_pct := 0;
        ELSE
            v_pct := ROUND((v_price - v_net) / v_price * 100, 2);
        END IF;
        NEW.discount_bath := v_net;
        NEW.discount_pct := v_pct;

    ELSIF v_source = 'pct' THEN
        v_pct := ROUND(COALESCE(NEW.discount_pct::NUMERIC, 0), 2);
        v_net := ROUND(v_price * (1 - v_pct / 100), 2);
        NEW.discount_pct := v_pct;
        NEW.discount_bath := v_net;
    END IF;

    -- Quantity-only changes preserve the net price to avoid rounding drift.
    -- The net unit price already has the discount deducted.
    NEW.total_price := ROUND(
        NEW.discount_bath::NUMERIC * NEW.quantity::NUMERIC,
        2
    );

    -- Modify the pending row directly; no recursive UPDATE is needed.
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_bom_discount_total ON pjtrk.bom_and_costing;

CREATE TRIGGER trg_bom_discount_total
BEFORE INSERT OR UPDATE ON pjtrk.bom_and_costing
FOR EACH ROW
EXECUTE FUNCTION pjtrk.fn_bom_discount_total();

COMMIT;

-- Example: replace <primary_key_column> and <row_id> with your actual key.
-- UPDATE public.bom_and_costing
-- SET discount_pct = 20.02
-- WHERE <primary_key_column> = <row_id>
-- RETURNING quantity, unit_price, discount_bath, discount_pct, total_price;
-- For unit_price = 2000 and quantity = 5:
-- discount_bath = 1599.60; total_price = 7998.00.

-- Net unit price entry:
-- UPDATE public.bom_and_costing
-- SET discount_bath = 1900
-- WHERE <primary_key_column> = <row_id>
-- RETURNING discount_bath, discount_pct, total_price;
-- For unit_price = 2000 and quantity = 5:
-- discount_pct = 5.00; total_price = 9500.00.

-- Optional ONE-TIME conversion of existing rows using their current percentage.
-- Installation alone does not recalculate existing rows.
-- The trigger derives the percentage from any changed net price, so rounding
-- may adjust the stored percentage slightly. Review before running on all rows.
-- UPDATE public.bom_and_costing
-- SET discount_bath = ROUND(unit_price::NUMERIC * (1 - COALESCE(discount_pct::NUMERIC, 0) / 100), 2)
-- WHERE unit_price IS NOT NULL;

-- Policy notes:
-- Setting either edited field to NULL resets to no discount (pct 0, net price
-- equal to unit_price, rounded to 2 places).
-- The net price and percentage may differ algebraically by rounding.
-- unit_price-only changes preserve the stored percentage.
-- quantity NULL gives total_price NULL (no implicit quantity is assumed).
-- Existing range constraints, if any, still apply. This script adds none.
-- All five columns must be ordinary columns, not GENERATED columns.
-- Documentation: https://www.postgresql.org/docs/current/plpgsql-trigger.html
