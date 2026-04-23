import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LandingPage } from "./LandingPage";

describe("LandingPage", () => {
  it("renders the app name and sign-in button", () => {
    render(<LandingPage />);
    expect(screen.getByRole("heading", { name: /poe2 hideout butler/i })).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /sign in with ggg/i });
    expect(link).toHaveAttribute("href", "/api/auth/login");
    expect(
      screen.getByText(/this product isn't affiliated with or endorsed by grinding gear games/i),
    ).toBeInTheDocument();
  });
});
