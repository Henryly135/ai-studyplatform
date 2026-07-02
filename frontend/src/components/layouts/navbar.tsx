import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { clearStoredSession, getStoredCurrentUser } from "../../services/api";

function Navbar() {
    const navigate = useNavigate();
    const [userName, setUserName] = useState<string | null>(() => {
        return getStoredCurrentUser()?.userName || null;
    });

    const handleLogout = () => {
        clearStoredSession();
        setUserName(null);
        navigate("/login");
    };

    return (
        <header className="navbar">
            <Link to="/" className="brand">学习平台
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
                                <Link to="/change-password" className="dropdown-item">修改密码
                                </Link>
                            </li>
                            <li><hr className="dropdown-divider" /></li>
                            <li>
                                <button className="dropdown-item" onClick={handleLogout}>退出登录
                                </button>
                            </li>
                        </ul>
                    </div>
                ) : (
                    <>
                        <Link to="/login" className="login-link">登录
                        </Link>

                        <div className="dropdown">
                            <button
                                className="btn btn-secondary dropdown-toggle"
                                type="button"
                                data-bs-toggle="dropdown"
                            >注册
                            </button>

                            <ul className="dropdown-menu">
                                <li>
                                    <Link to="/register/learner" className="dropdown-item">学生
                                    </Link>
                                </li>
                                <li>
                                    <Link to="/register/educator" className="dropdown-item">教师
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
