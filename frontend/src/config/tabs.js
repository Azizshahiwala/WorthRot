import React from "react";
import App from "../App.jsx";
import AboutPage from "../pages/AboutPage.jsx";
import ComparePage from "../pages/ComparePage.jsx";
import HistoryPage from "../pages/HistoryPage.jsx";
import InstagramPage from "../pages/InstagramPage.jsx";

export const tabs = [
  { label: "YouTube", path: "/", element: React.createElement(App), enabled: true },
  {
    label: "Compare",
    path: "/compare",
    element: React.createElement(ComparePage),
    enabled: false,
  },
  {
    label: "Instagram",
    path: "/instagram",
    element: React.createElement(InstagramPage),
    enabled: false,
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
    enabled: false,
  },
];
