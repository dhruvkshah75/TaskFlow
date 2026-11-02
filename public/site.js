(() => {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const observer = new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("visible");
          observer.unobserve(e.target);
        }
      }),
    { threshold: 0.12 },
  );
  if (!reduced.matches) {
    document.documentElement.classList.add("js-motion");
    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
  }
  const tagline = document.querySelector(".word-reveal");
  let wordIndex = 0;
  const wordObserver = new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("lit");
          wordObserver.unobserve(e.target);
        }
      }),
    { rootMargin: "0px 0px -25% 0px", threshold: 1 },
  );
  [...(tagline?.childNodes || [])].forEach((node) => {
    if (node.nodeType === 3) {
      const fragment = document.createDocumentFragment();
      node.textContent.split(/(\s+)/).forEach((word) => {
        if (!word.trim()) {
          fragment.append(document.createTextNode(word));
          return;
        }
        const span = document.createElement("span");
        span.className = "word";
        span.style.transitionDelay = wordIndex++ * 50 + "ms";
        span.textContent = word;
        fragment.append(span);
        if (!reduced.matches) wordObserver.observe(span);
        else span.classList.add("lit");
      });
      node.replaceWith(fragment);
    }
  });
  const pods = document.querySelector("#pods");
  for (let i = 0; pods && i < 20; i++) {
    const pod = document.createElement("span");
    pod.className = "pod mono caption-4" + (i < 2 ? " active" : "");
    pod.textContent = "·";
    pods.append(pod);
  }
  document.querySelectorAll(".scale-button").forEach((button) =>
    button.addEventListener("click", () => {
      document
        .querySelectorAll(".scale-button")
        .forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      const count = Number(button.dataset.workers);
      document.querySelector("#worker-count").textContent = String(
        count,
      ).padStart(2, "0");
      [...pods.children].forEach((pod, i) => {
        pod.style.transitionDelay = reduced.matches ? "0ms" : i * 20 + "ms";
        pod.classList.toggle("active", i < count);
      });
      document.querySelector("#scale-message").textContent =
        count === 2
          ? "Baseline capacity. Ready for work."
          : count === 10
            ? "Queue grows. More workers take tasks."
            : "Peak capacity. The fleet scales out.";
    }),
  );
  const pause = document.querySelector("#pause-motion");
  pause?.addEventListener("click", () => {
    const paused = pause.getAttribute("aria-pressed") !== "true";
    pause.setAttribute("aria-pressed", String(paused));
    pause.textContent = paused ? "Play" : "Pause";
    document
      .querySelector("#execution-console")
      .classList.toggle("paused", paused);
  });
  function setWires() {
    document
      .querySelectorAll(".wire")
      .forEach((w) =>
        w.style.setProperty("--travel", Math.max(0, w.clientWidth - 5) + "px"),
      );
  }
  const pipeline = document.querySelector(".pipeline");
  if (pipeline) {
    new ResizeObserver(setWires).observe(pipeline);
    setWires();
  }
  const toggle = document.querySelector(".menu-toggle"),
    menu = document.querySelector("#mobile-menu");
  function closeMenu() {
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation");
    menu.classList.remove("open");
    menu.inert = true;
    document.body.style.overflow = "";
  }
  toggle.addEventListener("click", () => {
    if (toggle.getAttribute("aria-expanded") === "true") {
      closeMenu();
      return;
    }
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close navigation");
    menu.classList.add("open");
    menu.inert = false;
    document.body.style.overflow = "hidden";
    menu.querySelector("a").focus();
  });
  menu
    .querySelectorAll("a")
    .forEach((a) => a.addEventListener("click", closeMenu));
  document.addEventListener("keydown", (e) => {
    if (toggle.getAttribute("aria-expanded") !== "true") return;
    if (e.key === "Escape") {
      closeMenu();
      toggle.focus();
    }
    if (e.key === "Tab") {
      const elements = [toggle, ...menu.querySelectorAll("a")],
        first = elements[0],
        last = elements[elements.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
  matchMedia("(min-width:761px)").addEventListener("change", (e) => {
    if (e.matches) closeMenu();
  });
  document.querySelectorAll(".copy").forEach((button) =>
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(
          button.previousElementSibling.textContent,
        );
        button.textContent = "Copied";
        document.querySelector("#copy-status").textContent =
          "Command copied to clipboard.";
        setTimeout(() => (button.textContent = "Copy"), 2000);
      } catch {
        button.textContent = "Select text";
        document.querySelector("#copy-status").textContent =
          "Copy unavailable. Select and copy the command above.";
      }
    }),
  );
  reduced.addEventListener("change", () => {
    if (reduced.matches) {
      document.documentElement.classList.remove("js-motion");
      document.querySelectorAll(".word").forEach((w) => w.classList.add("lit"));
    }
  });
})();
