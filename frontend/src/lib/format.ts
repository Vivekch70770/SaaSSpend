export const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");
export const lakh = (n: number) => "₹" + (n / 1e5).toFixed(1) + "L";
