import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { MetaFields, TEACHER_FIELDS, fillTeacher, teachersFrom } from "./TeacherForm";

afterEach(cleanup);

const projects: { meta: Record<string, string> }[] = [
  { meta: { oqituvchi: "Asadov Shavkat", ish_joyi: "Gumanitar fanlar maktabi", lavozim: "dotsent", fan: "Huquq" } },
  { meta: { oqituvchi: "Asadov Shavkat", lavozim: "professori", ilmiy_unvon: "Yuridik fanlari doktori" } },
  { meta: { oqituvchi: "Noʻmonzoda Sanjarbek", ish_joyi: "Xorijiy tillar maktabi", lavozim: "oʻqituvchisi" } },
  { meta: { fan: "ismsiz" } },
];

describe("o'qituvchi takliflari", () => {
  it("avvalgi darslardan: oxirgisi ustun, bo'sh qiymat eskisini o'chirmaydi", () => {
    const t = teachersFrom(projects);
    expect([...t.keys()]).toEqual(["Asadov Shavkat", "Noʻmonzoda Sanjarbek"]);
    expect(t.get("Asadov Shavkat")).toEqual({ oqituvchi: "Asadov Shavkat", ish_joyi: "Gumanitar fanlar maktabi",
      lavozim: "professori", ilmiy_unvon: "Yuridik fanlari doktori", fan: "Huquq" });
  });
  it("ism tanlansa qolgan maydonlar to'ldiriladi, kiritilgan fan saqlanadi", () => {
    const t = teachersFrom(projects);
    expect(fillTeacher({ oqituvchi: "Asadov Shavkat", fan: "Konstitutsiyaviy huquq" }, t)).toMatchObject({
      lavozim: "professori", ish_joyi: "Gumanitar fanlar maktabi", fan: "Konstitutsiyaviy huquq" });
    expect(fillTeacher({ oqituvchi: "Asadov" }, t)).toEqual({ oqituvchi: "Asadov" });   // to'liq mos emas
  });
  it("ism maydonida ro'yxat; tanlash maydonlarni to'ldiradi", () => {
    const onChange = vi.fn();
    const { container } = render(<MetaFields fields={TEACHER_FIELDS} meta={{}} onChange={onChange} teachers={teachersFrom(projects)} />);
    expect([...container.querySelectorAll("#known-teachers option")].map((o) => (o as HTMLOptionElement).value))
      .toEqual(["Asadov Shavkat", "Noʻmonzoda Sanjarbek"]);
    fireEvent.change(container.querySelector("input[list=known-teachers]")!, { target: { value: "Noʻmonzoda Sanjarbek" } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ ish_joyi: "Xorijiy tillar maktabi", lavozim: "oʻqituvchisi" }));
  });
});
