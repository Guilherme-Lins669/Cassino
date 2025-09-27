// static/js/main.js
document.addEventListener("DOMContentLoaded", () => {
  // --- forms de jogo (id terminando em "-form") ---
  const forms = document.querySelectorAll("form[id$='-form']");

  forms.forEach(form => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const game = form.id.replace("-form", "");
      const formData = new FormData(form);

      try {
        const res = await fetch(`/play/${game}`, {
          method: "POST",
          body: formData
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: 'Erro desconhecido' }));
          throw new Error(err.error || 'Erro ao jogar');
        }

        const data = await res.json();

        const saldoEl = document.getElementById("saldo");
        if (saldoEl) saldoEl.textContent = Number(data.saldo).toFixed(2);

        const resultadoDiv = document.getElementById("resultado");
        if (resultadoDiv) {
          resultadoDiv.innerHTML = `
            <p>${data.resultado || ''}</p>
            <p>Você apostou R$ ${Number(data.bet).toFixed(2)}</p>
            <p>Payout: R$ ${Number(data.payout).toFixed(2)}</p>
            <p>Tempo de jogo: ${data.duration || 0}s</p>
            <button onclick="location.reload()">Jogar novamente</button>
            <a href="/lobby">Voltar ao Lobby</a>
          `;
        }
      } catch (error) {
        console.error(error);
        const resultadoDiv = document.getElementById("resultado");
        if (resultadoDiv) resultadoDiv.textContent = `Erro: ${error.message}`;
      }
    });
  });

  // --- Dropdown do usuário ---
  const userBtn = document.getElementById("userBtn");
  const dropdownMenu = document.getElementById("dropdownMenu");
  if (userBtn) {
    userBtn.addEventListener("click", () => {
      if (dropdownMenu.style.display === "none") dropdownMenu.style.display = "block";
      else dropdownMenu.style.display = "none";
    });
    // fechar ao clicar fora
    document.addEventListener("click", (e) => {
      if (!userBtn.contains(e.target) && !dropdownMenu.contains(e.target)) {
        dropdownMenu.style.display = "none";
      }
    });
  }

  // --- Modal de depósito ---
  const depositOpenBtn = document.getElementById("depositOpenBtn");
  const depositModal = document.getElementById("depositModal");
  const depositClose = document.getElementById("depositClose");
  const depositForm = document.getElementById("deposit-form");
  const depositError = document.getElementById("depositError");
  const saldoEl = document.getElementById("saldo");

  if (depositOpenBtn && depositModal) {
    depositOpenBtn.addEventListener("click", () => {
      depositError.style.display = "none";
      depositError.textContent = "";
      depositModal.style.display = "block";
      // esconder dropdown
      if (dropdownMenu) dropdownMenu.style.display = "none";
    });
  }

  if (depositClose) {
    depositClose.addEventListener("click", () => {
      depositModal.style.display = "none";
    });
  }

  // submit via AJAX para /deposit
  if (depositForm) {
    depositForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      depositError.style.display = "none";
      depositError.textContent = "";

      const formData = new FormData(depositForm);
      const amount = formData.get("amount");

      try {
        const res = await fetch("/deposit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount })
        });

        const data = await res.json();

        if (!res.ok) {
          depositError.style.display = "block";
          depositError.textContent = data.error || "Erro no depósito";
          return;
        }

        // sucesso: atualizar saldo na UI e fechar modal
        if (saldoEl) saldoEl.textContent = Number(data.balance).toFixed(2);
        depositModal.style.display = "none";
      } catch (err) {
        console.error(err);
        depositError.style.display = "block";
        depositError.textContent = "Erro ao chamar o servidor";
      }
    });
  }

  // fechar modal ao clicar fora do conteúdo
  window.addEventListener("click", (e) => {
    if (e.target === depositModal) {
      depositModal.style.display = "none";
    }
  });
});
