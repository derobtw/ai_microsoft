const revealElements = document.querySelectorAll(".reveal");

const observer = new IntersectionObserver(
    (entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("visible");
                observer.unobserve(entry.target);
            }
        });
    },
    {
        threshold: 0.16
    }
);

revealElements.forEach((element, index) => {
    element.style.transitionDelay = `${Math.min(index * 70, 420)}ms`;
    observer.observe(element);
});

const header = document.querySelector(".site-header");

window.addEventListener("scroll", () => {
    const scrolled = window.scrollY > 24;
    header.style.boxShadow = scrolled
        ? "0 12px 30px rgba(15, 23, 42, 0.08)"
        : "none";
});

const flowNodes = document.querySelectorAll(".flow-node");
let activeFlowIndex = 0;

setInterval(() => {
    flowNodes.forEach((node) => node.classList.remove("active"));
    flowNodes[activeFlowIndex].classList.add("active");
    activeFlowIndex = (activeFlowIndex + 1) % flowNodes.length;
}, 1200);
