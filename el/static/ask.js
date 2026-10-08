// Morning brief: ask Hermes to write today's brief, then reload to show it.
(function () {
  const button = document.getElementById("brief-button");
  if (!button) return;
  const status = document.getElementById("brief-status");
  button.addEventListener("click", async () => {
    button.disabled = true;
    status.textContent = "Hermes is writing the brief…";
    try {
      const response = await fetch("/api/brief", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      window.location.reload();
    } catch (error) {
      status.textContent = `Couldn't write the brief: ${error.message}`;
      button.disabled = false;
    }
  });
})();

// Ask E-L: send the question to /api/ask and show Hermes's reply as plain text.
(function () {
  const form = document.getElementById("ask-form");
  if (!form) return;
  const input = document.getElementById("ask-input");
  const answer = document.getElementById("ask-answer");
  const button = form.querySelector("button");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    button.disabled = true;
    answer.hidden = false;
    answer.classList.remove("is-error");
    answer.textContent = "Thinking…";
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      answer.textContent = data.answer;
    } catch (error) {
      answer.classList.add("is-error");
      answer.textContent = `Couldn't reach E-L: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  });
})();
