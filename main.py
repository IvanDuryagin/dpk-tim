"""
Программа демонстрации концепции «ТИМ-ДПК»:
Автоматическое извлечение данных об узлах CLT/ДПК-панелей из IFC и формирование JSON-спецификации.

Инструкция по установке зависимостей:
    pip install ifcopenshell   # опционально, для реального парсинга IFC
Для работы tkinter дополнительных пакетов не требуется (встроен в Python).
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import sys
from datetime import datetime

# Попытка импорта ifcopenshell
try:
    import ifcopenshell
    IFCOS_AVAILABLE = True
except ImportError:
    IFCOS_AVAILABLE = False


class DemoIfcParser:
    """Класс-заглушка, возвращающий демонстрационные данные о CLT-панелях."""
    
    @staticmethod
    def get_panels():
        """Возвращает список словарей с данными демонстрационных панелей."""
        return [
            {
                "guid": "3kL2n9H5x8pR7sT1vB4w",
                "thickness_mm": 120,
                "material": "CLT 120 C24",
                "bbox": {  # минимальные/максимальные координаты в мм
                    "min": (0, 0, 0),
                    "max": (3000, 120, 2500)
                },
                "orientation": (0, 1, 0)  # пример ориентации слоёв
            },
            {
                "guid": "7fD8gE2rF1tY5uJ9iK6h",
                "thickness_mm": 160,
                "material": "CLT 160 C24",
                "bbox": {
                    "min": (3000, 0, 0),
                    "max": (3160, 3000, 2500)
                },
                "orientation": (1, 0, 0)
            },
            {
                "guid": "2aB4cD6eF8gH0iJ2kL4m",
                "thickness_mm": 100,
                "material": "CLT 100 C24",
                "bbox": {
                    "min": (0, 3000, 0),
                    "max": (3000, 3100, 2500)
                },
                "orientation": (0, 0, 1)
            },
        ]


class RealIfcParser:
    """Класс для реального парсинга IFC с помощью ifcopenshell."""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.model = ifcopenshell.open(filepath)
    
def get_clt_panels(self):
    """Извлекает данные о CLT-панелях из IFC (как IfcPlate, так и IfcWall)."""
    panels = []
    
    # Собираем все элементы, которые могут быть панелями: плиты и стены
    elements = []
    elements.extend(self.model.by_type("IfcPlate"))
    elements.extend(self.model.by_type("IfcWall"))
    
    for element in elements:
        # Проверка материала на наличие ключевых слов
        material_name = self._get_material_name(element)
        if not material_name:
            continue
        if not any(kw in material_name.lower() for kw in ["clt", "дпк", "cross-laminated"]):
            continue
        
        # GUID
        guid = element.GlobalId
        
        # Толщина из IfcMaterialLayerSet
        thickness = self._get_thickness(element)
        
        # Упрощённый bounding box
        bbox = self._get_bbox(element)
        
        panels.append({
            "guid": guid,
            "thickness_mm": thickness,
            "material": material_name,
            "bbox": bbox,
            "orientation": (0, 1, 0)  # для упрощения
        })
    
    return panels
    
    def _get_material_name(self, plate):
        """Возвращает имя материала панели или None."""
        # Упрощённо: ищем через IfcRelAssociatesMaterial
        for rel in getattr(plate, 'HasAssociations', []):
            if rel.is_a("IfcRelAssociatesMaterial"):
                material_select = rel.RelatingMaterial
                if material_select.is_a("IfcMaterial"):
                    return material_select.Name
                elif material_select.is_a("IfcMaterialLayerSetUsage"):
                    layer_set = material_select.ForLayerSet
                    if layer_set and layer_set.MaterialLayers:
                        first_layer = layer_set.MaterialLayers[0]
                        if first_layer.Material:
                            return first_layer.Material.Name
        return None
    
    def _get_thickness(self, plate):
        """Возвращает суммарную толщину слоёв панели в мм."""
        thickness = 0
        for rel in getattr(plate, 'HasAssociations', []):
            if rel.is_a("IfcRelAssociatesMaterial"):
                material_select = rel.RelatingMaterial
                if material_select.is_a("IfcMaterialLayerSetUsage"):
                    layer_set = material_select.ForLayerSet
                    if layer_set:
                        for layer in layer_set.MaterialLayers:
                            thickness += layer.LayerThickness
        # Если не найдено, возвращаем значение по умолчанию
        return thickness if thickness > 0 else 120
    
    def _get_bbox(self, plate):
        """Возвращает приближённый bounding box (для демо генерируется на основе GUID)."""
        # В реальном приложении здесь нужно использовать ifcopenshell.geom.create_shape()
        # Для простоты генерируем bbox на основе хеша GUID
        hash_val = hash(plate.GlobalId) % 5000
        return {
            "min": (0, 0, 0),
            "max": (3000 + hash_val, 120 + hash_val % 100, 2500)
        }


class TimDpkApp:
    """Главное окно приложения ТИМ-ДПК."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("ТИМ-ДПК – автоматизация переноса данных узлов ДПК")
        self.root.geometry("900x750")
        
        # Переменные состояния
        self.ifc_path = tk.StringVar()
        self.panels_data = []
        self.nodes_data = []
        self.full_json = {}
        
        self.create_widgets()
        self.log("Приложение запущено. Добро пожаловать!")
        if not IFCOS_AVAILABLE:
            self.log("Библиотека ifcopenshell не найдена. Будет использован демонстрационный режим.")
    
    def create_widgets(self):
        """Создание всех элементов интерфейса."""
        # Главный фрейм с отступами
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="ТИМ-ДПК – Автоматизация переноса данных узлов ДПК",
                                font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Блок выбора файла
        file_frame = ttk.LabelFrame(main_frame, text="IFC-файл", padding="5")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_frame, text="Путь:").grid(row=0, column=0, sticky=tk.W)
        path_entry = ttk.Entry(file_frame, textvariable=self.ifc_path, width=70)
        path_entry.grid(row=0, column=1, padx=(5, 5), sticky=tk.EW)
        ttk.Button(file_frame, text="Загрузить IFC", command=self.load_ifc).grid(row=0, column=2)
        file_frame.columnconfigure(1, weight=1)
        
        # Панель кнопок управления
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(btn_frame, text="Анализ и формирование JSON",
                   command=self.analyze_and_generate).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Сохранить JSON",
                   command=self.save_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Настройки",
                   command=self.settings_stub).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="О программе",
                   command=self.about).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Помощь",
                   command=self.help_stub).pack(side=tk.LEFT, padx=2)
        
        # Рамка со статистикой
        stats_frame = ttk.LabelFrame(main_frame, text="Статистика модели", padding="5")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.panels_count_var = tk.StringVar(value="0")
        self.nodes_count_var = tk.StringVar(value="0")
        ttk.Label(stats_frame, text="CLT-панелей:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Label(stats_frame, textvariable=self.panels_count_var, font=("Arial", 10, "bold")).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(stats_frame, text="Обнаружено узлов:").grid(row=0, column=2, sticky=tk.W, padx=(20,5))
        ttk.Label(stats_frame, textvariable=self.nodes_count_var, font=("Arial", 10, "bold")).grid(row=0, column=3, sticky=tk.W, padx=5)
        
        # Лог действий
        log_frame = ttk.LabelFrame(main_frame, text="Лог выполнения", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state='disabled', wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Предпросмотр JSON
        json_frame = ttk.LabelFrame(main_frame, text="Предпросмотр JSON-спецификации", padding="5")
        json_frame.pack(fill=tk.BOTH, expand=True)
        
        self.json_text = scrolledtext.ScrolledText(json_frame, height=12, wrap=tk.WORD)
        self.json_text.pack(fill=tk.BOTH, expand=True)
    
    def log(self, message):
        """Добавление сообщения в лог."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.root.update_idletasks()
    
    def load_ifc(self):
        """Открывает диалог выбора IFC-файла и сохраняет путь."""
        filetypes = [("IFC files", "*.ifc"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(title="Выберите IFC-файл",
                                              filetypes=filetypes)
        if filename:
            self.ifc_path.set(filename)
            self.log(f"Выбран файл: {os.path.basename(filename)}")
    
    def analyze_and_generate(self):
        """Основная логика: анализ IFC и формирование JSON."""
        if not self.ifc_path.get():
            messagebox.showwarning("Нет файла", "Сначала выберите IFC-файл.")
            return
        
        self.log("=" * 50)
        self.log("Запуск анализа модели...")
        self.panels_data = []
        self.nodes_data = []
        
        # Очистка статистики и JSON
        self.panels_count_var.set("0")
        self.nodes_count_var.set("0")
        self.json_text.delete(1.0, tk.END)
        
        # Выбор метода парсинга
        if IFCOS_AVAILABLE and os.path.exists(self.ifc_path.get()):
            try:
                self.log("Попытка реального парсинга IFC с помощью ifcopenshell...")
                parser = RealIfcParser(self.ifc_path.get())
                self.panels_data = parser.get_clt_panels()
                self.log(f"Реальный анализ: найдено {len(self.panels_data)} панелей.")
            except Exception as e:
                self.log(f"Ошибка при реальном парсинге: {e}")
                self.log("Переключение на демонстрационный режим...")
                self.panels_data = DemoIfcParser.get_panels()
        else:
            self.log("Используется демонстрационный набор данных (ifcopenshell отсутствует).")
            self.panels_data = DemoIfcParser.get_panels()
        
        if not self.panels_data:
            self.log("CLT-панели не найдены.")
            self.panels_count_var.set("0")
            return
        
        self.log(f"Ищем панели... Найдено {len(self.panels_data)} панелей.")
        self.panels_count_var.set(str(len(self.panels_data)))
        
        # Определение узлов (пересечения bounding box)
        self.log("Выполняется поиск узлов соединения...")
        self.nodes_data = self.detect_nodes(self.panels_data)
        self.log(f"Обнаружено {len(self.nodes_data)} узлов.")
        self.nodes_count_var.set(str(len(self.nodes_data)))
        
        # Формирование полного JSON
        self.log("Формирование JSON-спецификации...")
        self.full_json = self.build_json_spec(self.panels_data, self.nodes_data)
        self.log("JSON сформирован.")
        
        # Отображение JSON в текстовом поле
        json_str = json.dumps(self.full_json, indent=2, ensure_ascii=False)
        self.json_text.delete(1.0, tk.END)
        self.json_text.insert(tk.END, json_str)
        
        self.log("Анализ завершён успешно.")
    
    def detect_nodes(self, panels):
        """
        Определяет узлы на основе пересечения bounding box панелей.
        Возвращает список узлов.
        """
        nodes = []
        n = len(panels)
        used_pairs = set()
        
        for i in range(n):
            for j in range(i+1, n):
                if (i, j) in used_pairs or (j, i) in used_pairs:
                    continue
                if self.bbox_intersect(panels[i]["bbox"], panels[j]["bbox"]):
                    # Определяем тип соединения по взаимной ориентации (упрощённо)
                    orientation1 = panels[i].get("orientation", (0,1,0))
                    orientation2 = panels[j].get("orientation", (0,1,0))
                    # Если скалярное произведение близко к 0 -> перпендикулярны (угол)
                    dot = sum(a*b for a,b in zip(orientation1, orientation2))
                    if abs(dot) < 0.1:
                        conn_type = "corner" if i == 0 else "T-shaped"
                    else:
                        conn_type = "butt"
                    
                    node_id = f"UZEL-{len(nodes)+1}"
                    nodes.append({
                        "node_id": node_id,
                        "connection_type": conn_type,
                        "panels": [
                            {"guid": panels[i]["guid"], "thickness_mm": panels[i]["thickness_mm"],
                             "layer_orientation": panels[i]["orientation"]},
                            {"guid": panels[j]["guid"], "thickness_mm": panels[j]["thickness_mm"],
                             "layer_orientation": panels[j]["orientation"]}
                        ],
                        "geometry": {
                            "contact_area_mm2": 15000,  # демо-значение
                            "angle_deg": 90 if conn_type in ("corner", "T-shaped") else 0
                        }
                    })
                    used_pairs.add((i, j))
        
        return nodes
    
    @staticmethod
    def bbox_intersect(bbox1, bbox2):
        """Проверка пересечения двух параллелепипедов, заданных min/max."""
        min1, max1 = bbox1["min"], bbox1["max"]
        min2, max2 = bbox2["min"], bbox2["max"]
        return (min1[0] <= max2[0] and max1[0] >= min2[0] and
                min1[1] <= max2[1] and max1[1] >= min2[1] and
                min1[2] <= max2[2] and max1[2] >= min2[2])
    
    def build_json_spec(self, panels, nodes):
        """Создаёт итоговую JSON-спецификацию."""
        spec = {
            "project": "ТИМ-ДПК демонстрация",
            "timestamp": datetime.now().isoformat(),
            "nodes": nodes,
            "materials": {},
            "load_cases": []
        }
        # Добавляем информацию о материалах (уникальные материалы)
        materials = {}
        for panel in panels:
            mat_name = panel.get("material", "CLT")
            if mat_name not in materials:
                materials[mat_name] = {
                    "type": "CLT",
                    "thickness_mm": panel["thickness_mm"]
                }
        spec["materials"] = materials
        return spec
    
    def save_json(self):
        """Сохраняет сгенерированный JSON в файл."""
        if not self.full_json:
            messagebox.showinfo("Нет данных", "Сначала выполните анализ и сформируйте JSON.")
            return
        
        filename = filedialog.asksaveasfilename(defaultextension=".json",
                                                filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.full_json, f, indent=2, ensure_ascii=False)
                self.log(f"JSON сохранён в файл: {os.path.basename(filename)}")
                messagebox.showinfo("Сохранение", f"Файл успешно сохранён:\n{filename}")
            except Exception as e:
                self.log(f"Ошибка сохранения: {e}")
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")
    
    # Заглушки для демонстрационных кнопок
    def settings_stub(self):
        self.log("Настройки: функция в разработке.")
        messagebox.showinfo("Настройки", "Функция в разработке.\nЗдесь будут настройки алгоритмов поиска узлов.")
    
    def about(self):
        info = (
            "ТИМ-ДПК\n"
            "Автоматизация переноса данных узлов ДПК\n\n"
            "Версия 1.0.1\n"
            "Разработал https://github.com/IvanDuryagin."
        )
        messagebox.showinfo("О программе", info)
    
    def help_stub(self):
        help_text = (
            "Помощь:\n"
            "1. Нажмите «Загрузить IFC» и выберите файл.\n"
            "2. Нажмите «Анализ и формирование JSON» для обработки.\n"
            "3. Просмотрите статистику и JSON.\n"
            "4. Сохраните результат кнопкой «Сохранить JSON».\n\n"
            "При отсутствии библиотеки ifcopenshell используется демо-режим."
        )
        messagebox.showinfo("Помощь", help_text)


def main():
    root = tk.Tk()
    app = TimDpkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()