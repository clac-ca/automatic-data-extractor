export type DetectedMfaCodeKind = "otp" | "recovery" | "unknown";

const OTP_CODE_LENGTH = 6;
const RECOVERY_CODE_LENGTH = 8;
const RECOVERY_GROUP_LENGTH = 4;

export type ParsedMfaCode = Readonly<{
  kind: DetectedMfaCodeKind;
  alnum: string;
  digits: string;
  hasAlpha: boolean;
  hasHyphen: boolean;
  displayValue: string;
  submitValue: string;
  isOtpComplete: boolean;
  isRecoveryComplete: boolean;
  isComplete: boolean;
}>;

function normalizeAlnum(raw: string): string {
  return raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, RECOVERY_CODE_LENGTH);
}

function normalizeDigits(alnum: string): string {
  return alnum.replace(/\D/g, "");
}

function detectMfaCodeKind(
  alnum: string,
  digits: string,
  hasAlpha: boolean,
  hasHyphen: boolean,
): DetectedMfaCodeKind {
  if (alnum.length === 0) {
    return "unknown";
  }
  if (hasAlpha || hasHyphen || alnum.length === RECOVERY_CODE_LENGTH) {
    return "recovery";
  }
  if (alnum.length <= OTP_CODE_LENGTH && digits.length === alnum.length) {
    return "otp";
  }
  return "unknown";
}

export function formatRecoveryCode(alnum: string): string {
  const normalized = normalizeAlnum(alnum);
  if (normalized.length <= RECOVERY_GROUP_LENGTH) {
    return normalized;
  }
  return `${normalized.slice(0, RECOVERY_GROUP_LENGTH)}-${normalized.slice(RECOVERY_GROUP_LENGTH)}`;
}

export function parseMfaCode(raw: string): ParsedMfaCode {
  const hasHyphen = raw.includes("-");
  const alnum = normalizeAlnum(raw);
  const digits = normalizeDigits(alnum);
  const hasAlpha = /[A-Z]/.test(alnum);
  const kind = detectMfaCodeKind(alnum, digits, hasAlpha, hasHyphen);

  const displayValue = kind === "recovery" ? formatRecoveryCode(alnum) : alnum;
  const submitValue = kind === "recovery" ? formatRecoveryCode(alnum) : digits.slice(0, OTP_CODE_LENGTH);
  const isOtpComplete = kind === "otp" && digits.length === OTP_CODE_LENGTH;
  const isRecoveryComplete = kind === "recovery" && alnum.length === RECOVERY_CODE_LENGTH;
  const isComplete = isOtpComplete || isRecoveryComplete;

  return {
    kind,
    alnum,
    digits,
    hasAlpha,
    hasHyphen,
    displayValue,
    submitValue,
    isOtpComplete,
    isRecoveryComplete,
    isComplete,
  };
}

export function buildMfaInputError(parsed: ParsedMfaCode): string | null {
  if (parsed.isComplete) {
    return null;
  }
  return "Enter a 6-digit authenticator code or an 8-character recovery code.";
}
