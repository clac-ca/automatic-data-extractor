const EMAIL_PATTERN = /.+@.+\..+/;

interface ValidateEmailOptions {
  requiredMessage?: string;
  invalidMessage?: string;
  requireValue?: boolean;
}

export function validateEmail(value: string, options: ValidateEmailOptions = {}) {
  const {
    requiredMessage = "Enter an email",
    invalidMessage = "Enter a valid email",
    requireValue = true,
  } = options;

  const trimmed = value.trim();

  if (requireValue && trimmed.length === 0) {
    return requiredMessage;
  }

  if (trimmed.length > 0 && !EMAIL_PATTERN.test(trimmed)) {
    return invalidMessage;
  }

  return undefined;
}

interface ValidatePasswordOptions {
  requiredMessage?: string;
  minLength?: number;
  minLengthMessage?: string;
  requireComplexity?: boolean;
  complexityMessage?: string;
}

export function validatePassword(value: string, options: ValidatePasswordOptions = {}) {
  const {
    requiredMessage = "Enter your password",
    minLength,
    minLengthMessage,
    requireComplexity = false,
    complexityMessage = "Include uppercase, lowercase, and numeric characters",
  } = options;

  const messages: string[] = [];

  if (!value && requiredMessage) {
    messages.push(requiredMessage);
  }

  if (typeof minLength === "number" && value.length < minLength) {
    messages.push(minLengthMessage ?? `Password must be at least ${minLength} characters`);
  }

  if (requireComplexity) {
    if (!/[A-Z]/.test(value) || !/[a-z]/.test(value) || !/[0-9]/.test(value)) {
      messages.push(complexityMessage);
    }
  }

  if (messages.length > 0) {
    return messages.join(". ");
  }

  return undefined;
}

export function validateRequired(value: string, message: string) {
  if (value.trim() === "") {
    return message;
  }

  return undefined;
}

export function validateConfirmPassword(password: string, confirm: string, message = "Passwords must match") {
  if (password !== confirm) {
    return message;
  }

  return undefined;
}
