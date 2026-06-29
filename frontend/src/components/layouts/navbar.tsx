import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";

function Navbar() {
    const navigate = useNavigate();
    const [userName, setUserName] = useState<string | null>(() => {
        const stored = localStorage.getItem("currentUser");
        if (!stored) return null;
        try {
            const user = JSON.parse(stored);
            return user.userName ?? null;
        } catch {
            return null;
        }
    });

    const handleLogout = () => {
        localStorage.removeItem("accessToken");
        localStorage.removeItem("tokenType");
        localStorage.removeItem("currentUser");
        setUserName(null);
        navigate("/login");
    };

    return (
        <header className="navbar">
            <Link to="/" className="brand">
                EduLearning
            </Link>

            <div className="nav-actions">
                {userName ? (
                    <div className="dropdown">
                        <button
                            className="btn btn-secondary dropdown-toggle"
                            type="button"
                            data-bs-toggle="dropdown"
                        >
                            {userName}
                        </button>

                        <ul className="dropdown-menu dropdown-menu-end">
                            <li>
                                <Link to="/change-password" className="dropdown-item">
                                    Change Password
                                </Link>
                            </li>
                            <li><hr className="dropdown-divider" /></li>
                            <li>
                                <button className="dropdown-item" onClick={handleLogout}>
                                    Log out
                                </button>
                            </li>
                        </ul>
                    </div>
                ) : (
                    <>
                        <Link to="/login" className="login-link">
                            Log in
                        </Link>

                        <div className="dropdown">
                            <button
                                className="btn btn-secondary dropdown-toggle"
                                type="button"
                                data-bs-toggle="dropdown"
                            >
                                Sign up
                            </button>

                            <ul className="dropdown-menu">
                                <li>
                                    <Link to="/register/learner" className="dropdown-item">
                                        Learner
                                    </Link>
                                </li>
                                <li>
                                    <Link to="/register/educator" className="dropdown-item">
                                        Educator
                                    </Link>
                                </li>
                            </ul>
                        </div>
                    </>
                )}
            </div>
        </header>
    );
}

export default Navbar;
