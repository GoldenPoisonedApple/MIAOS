import { NavLink, Outlet } from "react-router-dom";
import styles from "./Layout.module.css";

export const Layout = () => {
  return (
    <div className={styles.appContainer}>
      <header className={styles.appHeader}>
        <h1>Dashboard</h1>
        <nav className={styles.tabNavigation}>
          <NavLink
            to="/experiments"
            className={({ isActive }) =>
              isActive ? `${styles.tabButton} ${styles.active}` : styles.tabButton
            }
          >
            実験一覧
          </NavLink>
          <NavLink
            to="/tasks"
            className={({ isActive }) =>
              isActive ? `${styles.tabButton} ${styles.active}` : styles.tabButton
            }
          >
            タスク一覧
          </NavLink>
          <NavLink
            to="/filters"
            className={({ isActive }) =>
              isActive ? `${styles.tabButton} ${styles.active}` : styles.tabButton
            }
          >
            フィルタ
          </NavLink>
        </nav>
      </header>
      <main className={styles.appMain}>
        <Outlet />
      </main>
    </div>
  );
};
