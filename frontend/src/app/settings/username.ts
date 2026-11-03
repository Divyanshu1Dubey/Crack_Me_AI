/**
 * The public username (handle) in Settings > Profile and on the sign-up form.
 *
 * Other learners see it on the leaderboard and in discussions. The backend
 * decides (PATCH /auth/profile/, accounts/handles.py: 3-30 letters, numbers,
 * `_` and `.`, unique, not an email address or part of the learner's own,
 * not a name reserved for the CrackLabs team); this mirrors the format rules
 * so most mistakes are shown before a request is sent. A name chosen at
 * sign-up that breaks those rules is replaced by a generated
 * `learner_<hex>` handle when the account is created.
 */
export const USERNAME_MIN_LENGTH = 3;
export const USERNAME_MAX_LENGTH = 30;
/** The format rule as an HTML `pattern` (the browser anchors it to the whole value). */
export const USERNAME_PATTERN = `[A-Za-z0-9_.]{${USERNAME_MIN_LENGTH},${USERNAME_MAX_LENGTH}}`;
export const USERNAME_HINT = 'Shown to other learners on the leaderboard and in discussions. 3–30 letters, numbers, _ or . (not your email address).';

/** True when `username` shows `email`: an '@', or its local part (any case, `_2` suffix, 140/130-char cut). */
export function usernameExposesEmail(username: string, email?: string | null): boolean {
    const name = username.trim().toLowerCase();
    if (!name) return false;
    if (name.includes('@')) return true;
    const local = (email || '').trim().toLowerCase().split('@', 1)[0].trim();
    if (!local) return false;
    const stems = new Set([name]);
    const cut = name.lastIndexOf('_');
    if (cut >= 0 && /^\d+$/.test(name.slice(cut + 1))) stems.add(name.slice(0, cut));
    return [local, local.slice(0, 140), local.slice(0, 130)].some((value) => stems.has(value));
}

/** Why `value` cannot be saved as the username, or null (the server still checks uniqueness and reserved names). */
export function usernameProblem(value: string, email?: string | null): string | null {
    const name = value.trim();
    if (name.includes('@')) return "Your username can't be an email address.";
    if (name.length < USERNAME_MIN_LENGTH || name.length > USERNAME_MAX_LENGTH) {
        return `Choose a username of ${USERNAME_MIN_LENGTH} to ${USERNAME_MAX_LENGTH} characters.`;
    }
    if (!/^[A-Za-z0-9_.]+$/.test(name)) return 'Use only letters, numbers, underscores (_) and dots (.).';
    if (!/[A-Za-z0-9]/.test(name)) return 'Include at least one letter or number.';
    if (usernameExposesEmail(name, email)) return "Choose a username that isn't part of your email address.";
    return null;
}

/**
 * The PATCH body for a profile save: `username` only when it changed, so a
 * username from before these rules never blocks saving the other fields.
 */
export function profileUpdatePayload(
    form: Record<string, string> & { username: string },
    currentUsername: string | null | undefined,
): Record<string, string> {
    const { username, ...rest } = form;
    const next = username.trim();
    return next !== (currentUsername || '') ? { ...rest, username: next } : rest;
}
