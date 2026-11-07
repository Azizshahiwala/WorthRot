import { useEffect, useRef, useState } from "react";
import { Menu, Moon, Sun, X } from "lucide-react";
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
        <NavLink
          className="brand"
          to="/"
          onClick={closeMenu}
          aria-label="WorthRot home"
        >
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
          {menuOpen ? (
            <X aria-hidden="true" size={18} />
          ) : (
            <Menu aria-hidden="true" size={18} />
          )}
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
          {theme === "light" ? (
            <Moon aria-hidden="true" size={16} />
          ) : (
            <Sun aria-hidden="true" size={16} />
          )}
          <span className="theme-label">{theme} mode</span>
        </Button>
      </div>
    </header>
  );
}
