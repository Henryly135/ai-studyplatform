import { useEffect, useMemo, useState } from "react";

import "./UserManagementPage.css";
import {
  getAdminUsers,
  updateAdminUserIdentity,
  updateAdminUserStatus,
} from "../../services/admin";
import UserManagementFilters from "./UserManagement/UserManagementFilters";
import UserManagementTable from "./UserManagement/UserManagementTable";
import { mapAdminUserToUserItem } from "./UserManagement/userManagementMappers";
import type {
  UserAccountStatus,
  UserItem,
  UserRole,
  UserRoleFilter,
} from "./UserManagement/types";
import { filterUsers } from "./UserManagement/userManagementUtils";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";

function UserManagementPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRoleFilter>("All");
  const [loading, setLoading] = useState(true);
  const [updatingUserUuid, setUpdatingUserUuid] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    return subscribeAppRefresh(["admin:users"], () => {
      setRefreshKey((current) => current + 1);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadUsers = async () => {
      const accessToken = localStorage.getItem("accessToken");

      if (!accessToken) {
        if (!cancelled) {
          setErrorMessage("Missing access token. Please log in again.");
          setLoading(false);
        }
        return;
      }

      try {
        const data = await getAdminUsers(accessToken);

        if (cancelled) {
          return;
        }

        setUsers(data.users.map(mapAdminUserToUserItem));
        setErrorMessage("");
      } catch (error) {
        if (cancelled) {
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : "Failed to fetch users."
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadUsers();

    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  useEffect(() => {
    if (!successMessage) {
      return;
    }

    const timer = window.setTimeout(() => {
      setSuccessMessage("");
    }, 2400);

    return () => {
      window.clearTimeout(timer);
    };
  }, [successMessage]);

  const filteredUsers = useMemo(() => {
    return filterUsers(users, search, roleFilter);
  }, [users, search, roleFilter]);

  const handleIdentityChange = async (userUuid: string, identity: UserRole) => {
    const accessToken = localStorage.getItem("accessToken");

    if (!accessToken) {
      setErrorMessage("Missing access token. Please log in again.");
      return;
    }

    try {
      setUpdatingUserUuid(userUuid);
      const updatedUser = await updateAdminUserIdentity(accessToken, userUuid, {
        identity,
      });

      setUsers((currentUsers) =>
        currentUsers.map((user) =>
          user.userUuid === userUuid ? mapAdminUserToUserItem(updatedUser) : user
        )
      );
      setErrorMessage("");
      emitAppRefresh({ scope: "admin:users" });
      setSuccessMessage("User identity updated successfully.");
    } catch (error) {
      setSuccessMessage("");
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to update user identity."
      );
    } finally {
      setUpdatingUserUuid(null);
    }
  };

  const handleStatusChange = async (
    userUuid: string,
    accountStatus: UserAccountStatus
  ) => {
    const accessToken = localStorage.getItem("accessToken");

    if (!accessToken) {
      setErrorMessage("Missing access token. Please log in again.");
      return;
    }

    try {
      setUpdatingUserUuid(userUuid);
      const updatedUser = await updateAdminUserStatus(accessToken, userUuid, {
        accountStatus,
      });

      setUsers((currentUsers) =>
        currentUsers.map((user) =>
          user.userUuid === userUuid ? mapAdminUserToUserItem(updatedUser) : user
        )
      );
      setErrorMessage("");
      emitAppRefresh({ scope: "admin:users" });
      setSuccessMessage("User status updated successfully.");
    } catch (error) {
      setSuccessMessage("");
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to update user status."
      );
    } finally {
      setUpdatingUserUuid(null);
    }
  };

  return (
    <section className="user-management-page">
      {successMessage ? (
        <div className="user-management-toast user-management-toast-success" role="status" aria-live="polite">
          <strong>Success</strong>
          <span>{successMessage}</span>
        </div>
      ) : null}

      <div className="user-management-card">
        <UserManagementFilters
          search={search}
          roleFilter={roleFilter}
          onSearchChange={setSearch}
          onRoleFilterChange={setRoleFilter}
        />

        {loading ? (
          <p className="user-management-feedback">Loading users...</p>
        ) : null}

        {!loading && errorMessage ? (
          <p className="user-management-feedback user-management-feedback-error">
            {errorMessage}
          </p>
        ) : null}

        {!loading && !errorMessage ? (
          <UserManagementTable
            users={filteredUsers}
            updatingUserUuid={updatingUserUuid}
            onIdentityChange={handleIdentityChange}
            onStatusChange={handleStatusChange}
          />
        ) : null}
      </div>
    </section>
  );
}

export default UserManagementPage;
