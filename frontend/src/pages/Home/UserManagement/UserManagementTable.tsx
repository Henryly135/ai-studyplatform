import type { UserAccountStatus, UserItem, UserRole } from "./types";

type UserManagementTableProps = {
  users: UserItem[];
  updatingUserUuid: string | null;
  onIdentityChange: (userUuid: string, identity: UserRole) => void;
  onStatusChange: (userUuid: string, accountStatus: UserAccountStatus) => void;
};

const IDENTITY_OPTIONS: UserRole[] = ["Educator", "Learner"];
const STATUS_OPTIONS: UserAccountStatus[] = [
  "active",
  "deactivated",
];

function formatIdentityLabel(identity: UserRole) {
  switch (identity) {
    case "Educator":
      return "教师";
    case "Learner":
      return "学生";
    case "Admin":
      return "管理员";
    default:
      return identity;
  }
}

function formatAccountStatusLabel(status: UserAccountStatus) {
  return status === "active" ? "启用" : "停用";
}

function UserManagementTable({
  users,
  updatingUserUuid,
  onIdentityChange,
  onStatusChange,
}: UserManagementTableProps) {
  return (
    <div className="user-management-table-wrapper">
      <table className="user-management-table">
        <thead>
          <tr>
            <th>姓名</th>
            <th>邮箱</th>
            <th>身份</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {users.length > 0 ? (
            users.map((user) => (
              <tr key={user.id}>
                <td>{user.name}</td>
                <td>{user.email}</td>
                <td>
                  <select
                    className="user-management-inline-select"
                    value={user.identity}
                    disabled={updatingUserUuid === user.userUuid}
                    onChange={(event) =>
                      onIdentityChange(user.userUuid, event.target.value as UserRole)
                    }
                  >
                    {IDENTITY_OPTIONS.map((identity) => (
                      <option key={identity} value={identity}>
                        {formatIdentityLabel(identity)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    className="user-management-inline-select"
                    value={user.accountStatus}
                    disabled={updatingUserUuid === user.userUuid}
                    onChange={(event) =>
                      onStatusChange(
                        user.userUuid,
                        event.target.value as UserAccountStatus
                      )
                    }
                  >
                    {STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>
                        {formatAccountStatusLabel(status)}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={4} className="empty-state">未找到用户。
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default UserManagementTable;
