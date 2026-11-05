import React from "react";
import App from "../App.jsx";
import AboutPage from "../pages/AboutPage.jsx";
import ComparePage from "../pages/ComparePage.jsx";
import HistoryPage from "../pages/HistoryPage.jsx";
import OtherPage from "../pages/OtherPage.jsx";

export const tabs = [
  { label: "YouTube", path: "/", element: React.createElement(App), enabled: true },
  {
    label: "Compare",
    path: "/compare",
    element: React.createElement(ComparePage),
    enabled: true,
  },
  {
    label: "Other",
    path: "/other",
    element: React.createElement(OtherPage),
    enabled: true,
  },
  {
    label: "History",
    path: "/history",
    element: React.createElement(HistoryPage),
    enabled: true,
  },
  {
    label: "About",
    path: "/about",
    element: React.createElement(AboutPage),
    enabled: true,
  },
];
