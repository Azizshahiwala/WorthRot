import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { tabs } from "../config/tabs.js";
import { useTheme } from "../contexts/ThemeContext.jsx";
import Button from "../components/ui/Button.jsx";

export default function NavBar() {
  const { theme, toggleTheme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef(null);

  useEffect(() => {
    if (!menuOpen) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [menuOpen]);

  function closeMenu() {
    setMenuOpen(false);
  }

  return (
    <header className="site-header">
      <div className="nav-inner">
        <NavLink className="brand" to="/" onClick={closeMenu}>
          <span className="brand-mark" aria-hidden="true">
            W
          </span>
          <span>WorthRot</span>
        </NavLink>

        <Button
          ref={menuButton}
          className="menu-toggle"
          variant="ghost"
          size="sm"
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          onClick={() => setMenuOpen((isOpen) => !isOpen)}
        >
          <span className="visually-hidden">
            {menuOpen ? "Close" : "Open"} navigation menu
          </span>
          <span aria-hidden="true">{menuOpen ? "×" : "☰"}</span>
        </Button>

        <nav
          id="primary-navigation"
          className={`primary-navigation${menuOpen ? " is-open" : ""}`}
          aria-label="Main"
        >
          <ul className="nav-list">
            {tabs.map((tab) => (
              <li key={tab.path}>
                <NavLink
                  className={({ isActive }) =>
                    `nav-link${isActive ? " is-active" : ""}`
                  }
                  to={tab.path}
                  onClick={closeMenu}
                  end={tab.path === "/"}
                >
                  <span>{tab.label}</span>
                  {!tab.enabled && (
                    <span className="nav-soon">Soon</span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <Button
          variant="ghost"
          size="sm"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
        >
          <span aria-hidden="true">{theme === "light" ? "☾" : "☀"}</span>
          <span className="theme-label">{theme} mode</span>
        </Button>
      </div>
    </header>
  );
}
