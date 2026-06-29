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
            <th>Name</th>
            <th>Email</th>
            <th>Identity</th>
            <th>Status</th>
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
                        {identity}
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
                        {status}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={4} className="empty-state">
                No users found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default UserManagementTable;
