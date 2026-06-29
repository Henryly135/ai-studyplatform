const PASSWORD_RULE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/;

export const PASSWORD_HINT = "Min 8 chars, A-Z, a-z, 0-9, special character";

export function validatePassword(password: string): string {
  if (!PASSWORD_RULE.test(password)) {
    return "Password must be at least 8 characters and include uppercase, lowercase, a number, and a special character.";
  }
  return "";
}
