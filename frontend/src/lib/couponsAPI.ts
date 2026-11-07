/**
 * Coupon codes (backend: accounts/coupons.py, accounts/views_coupons.py; 2026-11-07).
 *
 * Student: `validateCoupon` shows what a code is worth on /subscription; the code itself is applied by
 * `authAPI.subscribeOrder(plan, requestId, couponCode)`. A code worth the whole price answers
 * `{free_activation: true, subscription}` there: no Razorpay checkout.
 * Admin: create / edit / switch off codes and see who used them (/admin/coupons).
 */
import api from './api';
import type { PurchasablePlanId } from '@/app/subscription/plans';
import type { DiscountType } from './couponRules';

export type { DiscountType } from './couponRules';
export {
    couponErrorMessage, couponFromSearch, couponShareLink, describeDiscount, isoToLocalInput, localInputToIso,
    looksLikeCouponCode, normalizeCouponCode,
} from './couponRules';

export interface CouponPlanQuote {
    plan: PurchasablePlanId;
    original_amount: number;
    discount_amount: number;
    final_amount: number;
}

export interface CouponQuote {
    code: string;
    discount_type: DiscountType;
    discount_value: number;
    plans: Partial<Record<PurchasablePlanId, CouponPlanQuote>>;
}

export interface AdminCoupon {
    id: number;
    code: string;
    description: string;
    discount_type: DiscountType;
    discount_value: number;
    plans: PurchasablePlanId[];
    max_uses: number | null;
    max_uses_per_user: number;
    valid_from: string | null;
    valid_until: string | null;
    is_active: boolean;
    assigned_user: { id: number; username: string; email: string } | null;
    created_by: string | null;
    created_at: string | null;
    redeemed: number;
    checkouts_in_progress: number;
    discount_given: number;
    revenue: number;
    state: 'live' | 'off' | 'expired' | 'scheduled' | 'used_up';
}

export interface CouponRedemptionRow {
    id: number;
    coupon_id: number;
    code: string;
    user: { id: number; username: string; email: string } | null;
    plan: string;
    original_amount: number;
    discount_amount: number;
    final_amount: number;
    status: 'reserved' | 'released' | 'redeemed';
    razorpay_order_id: string;
    subscription_id: number | null;
    created_at: string | null;
    redeemed_at: string | null;
}

/** Fields an admin sends; `assigned_email` '' clears the personal assignment, `code` '' asks for a generated one. */
export interface CouponInput {
    code?: string;
    description?: string;
    discount_type?: DiscountType;
    discount_value?: number;
    plans?: PurchasablePlanId[];
    max_uses?: number | null;
    max_uses_per_user?: number;
    valid_from?: string | null;
    valid_until?: string | null;
    assigned_email?: string;
    is_active?: boolean;
}

export const couponsAPI = {
    validate: (code: string, plan?: PurchasablePlanId) =>
        api.post<CouponQuote>('/auth/coupons/validate/', { code, plan }),
    adminList: () => api.get<{ results: AdminCoupon[] }>('/auth/admin/coupons/'),
    adminCreate: (data: CouponInput) => api.post<AdminCoupon>('/auth/admin/coupons/', data),
    adminUpdate: (id: number, data: CouponInput) => api.patch<AdminCoupon>(`/auth/admin/coupons/${id}/`, data),
    adminDelete: (id: number) => api.delete(`/auth/admin/coupons/${id}/`),
    adminRedemptions: (params?: { coupon?: number; status?: CouponRedemptionRow['status'] }) =>
        api.get<{ results: CouponRedemptionRow[] }>('/auth/admin/coupons/redemptions/', { params }),
};

