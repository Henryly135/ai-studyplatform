const PASSWORD_RULE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/;

export const PASSWORD_HINT = "至少 8 位，包含大小写字母、数字和特殊字符";

export function validatePassword(password: string): string {
  if (!PASSWORD_RULE.test(password)) {
    return "密码至少 8 位，并且需要包含大写字母、小写字母、数字和特殊字符。";
  }
  return "";
}
