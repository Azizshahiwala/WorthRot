import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { tabs } from "./config/tabs.js";
import { AnalysisProvider } from "./contexts/AnalysisContext.jsx";
import { CompareProvider } from "./contexts/CompareContext.jsx";
import { OtherProvider } from "./contexts/OtherContext.jsx";
import { HistoryProvider } from "./contexts/HistoryContext.jsx";
import { RateLimitProvider } from "./contexts/RateLimitContext.jsx";
import { ThemeProvider } from "./contexts/ThemeContext.jsx";
import { ToastProvider } from "./contexts/ToastContext.jsx";
import Layout from "./layout/Layout.jsx";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <ThemeProvider>
        <ToastProvider>
          <HistoryProvider>
            <RateLimitProvider>
              <AnalysisProvider>
                <CompareProvider>
                  <OtherProvider>
                    <Routes>
                      <Route element={<Layout />}>
                        {tabs.map((tab) =>
                          tab.path === "/" ? (
                            <Route key={tab.path} index element={tab.element} />
                          ) : (
                            <Route
                              key={tab.path}
                              path={tab.path.slice(1)}
                              element={tab.element}
                            />
                          ),
                        )}
                        <Route path="*" element={<Navigate to="/" replace />} />
                      </Route>
                    </Routes>
                  </OtherProvider>
                </CompareProvider>
              </AnalysisProvider>
            </RateLimitProvider>
          </HistoryProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
