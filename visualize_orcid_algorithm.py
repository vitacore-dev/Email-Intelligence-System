#!/usr/bin/env python3
"""
Визуализация алгоритма ранжирования ORCID
Создает диаграммы и графики для анализа работы алгоритма
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from matplotlib.patches import Rectangle
import matplotlib.patches as mpatches

# Настройка стиля
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

def create_weight_distribution_chart():
    """Создает круговую диаграмму распределения весов факторов"""
    
    factors = ['Позиция в результатах', 'Прямой URL ORCID', 'Близость имени', 
              'Качество домена', 'Доменная аффинность', 'Полнота URL', 'Качество источника']
    weights = [25, 20, 15, 15, 10, 10, 5]
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF']
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Создаем круговую диаграмму
    wedges, texts, autotexts = ax.pie(weights, labels=factors, autopct='%1.0f%%', 
                                     colors=colors, startangle=90, textprops={'fontsize': 10})
    
    # Улучшаем внешний вид
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
    
    ax.set_title('🔬 Распределение весов факторов ранжирования ORCID', 
                fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig('orcid_weights_distribution.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_scoring_example():
    """Создает диаграмму примера расчета релевантности"""
    
    # Данные для примера с ORCID 0000-0003-2583-0599
    factors = ['Позиция\n(40/100)', 'Прямой URL\n(orcid.org)', 'Домен\n(orcid.org)', 
              'Близость имени\n(0.42)', 'Аффинность\n(0.30)', 'Качество\n(0.40)']
    weights = [0.25, 0.20, 0.15, 0.15, 0.10, 0.05]
    raw_scores = [0.60, 1.0, 1.0, 0.42, 0.30, 0.40]
    final_scores = [w * r for w, r in zip(weights, raw_scores)]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # График 1: Исходные оценки vs Финальные оценки
    x = np.arange(len(factors))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, raw_scores, width, label='Исходная оценка', 
                   color='lightblue', alpha=0.7)
    bars2 = ax1.bar(x + width/2, final_scores, width, label='Взвешенная оценка', 
                   color='darkblue', alpha=0.7)
    
    ax1.set_xlabel('Факторы')
    ax1.set_ylabel('Оценка')
    ax1.set_title('Расчет релевантности для ORCID 0000-0003-2583-0599')
    ax1.set_xticks(x)
    ax1.set_xticklabels(factors, rotation=45, ha='right')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Добавляем значения на столбцы
    for bar in bars2:
        height = bar.get_height()
        ax1.annotate(f'{height:.3f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')
    
    # График 2: Итоговый результат
    total_score = sum(final_scores)
    ax2.bar(['Итоговая релевантность'], [total_score], color='green', alpha=0.7, width=0.5)
    ax2.set_ylabel('Релевантность')
    ax2.set_title('Финальная оценка')
    ax2.set_ylim(0, 1)
    ax2.grid(True, alpha=0.3)
    
    # Добавляем значение
    ax2.annotate(f'{total_score:.3f}',
                xy=(0, total_score),
                xytext=(0, 10),
                textcoords="offset points",
                ha='center', va='bottom', 
                fontweight='bold', fontsize=14)
    
    plt.tight_layout()
    plt.savefig('orcid_scoring_example.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_ranking_comparison():
    """Создает сравнение всех найденных ORCID по релевантности"""
    
    # Данные из теста
    orcid_data = {
        'ORCID': ['0000-0003-4812-2165', '0000-0001-7928-2247', '0000-0002-5091-0518',
                 '0000-0003-2428-1559', '0000-0003-0202-5116', '0000-0002-6252-0322',
                 '0000-0002-8003-5523', '0000-0001-5638-3723', '0000-0001-9533-5556',
                 '0000-0002-1323-8072', '0000-0003-2583-0599'],
        'Релевантность': [0.63, 0.62, 0.62, 0.62, 0.61, 0.58, 0.58, 0.58, 0.57, 0.56, 0.61],
        'Позиция': [9, 12, 13, 15, 17, 28, 29, 31, 35, 37, 40],
        'Статус': ['Выбран', 'Кандидат', 'Кандидат', 'Кандидат', 'Кандидат', 
                  'Низкий', 'Низкий', 'Низкий', 'Низкий', 'Низкий', 'Референсный']
    }
    
    df = pd.DataFrame(orcid_data)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    
    # График 1: Релевантность всех ORCID
    colors = ['gold' if status == 'Выбран' 
             else 'red' if status == 'Референсный'
             else 'lightgreen' if status == 'Кандидат'
             else 'lightgray' for status in df['Статус']]
    
    bars = ax1.bar(range(len(df)), df['Релевантность'], color=colors, alpha=0.8)
    ax1.set_xlabel('ORCID ID')
    ax1.set_ylabel('Релевантность')
    ax1.set_title('Сравнение релевантности всех найденных ORCID')
    ax1.set_xticks(range(len(df)))
    ax1.set_xticklabels([orcid[-4:] for orcid in df['ORCID']], rotation=45)
    ax1.grid(True, alpha=0.3)
    
    # Добавляем значения на столбцы
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax1.annotate(f'{height:.2f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    # Легенда
    gold_patch = mpatches.Patch(color='gold', label='Выбранный')
    red_patch = mpatches.Patch(color='red', label='Референсный')
    green_patch = mpatches.Patch(color='lightgreen', label='Кандидат')
    gray_patch = mpatches.Patch(color='lightgray', label='Низкая релевантность')
    ax1.legend(handles=[gold_patch, red_patch, green_patch, gray_patch])
    
    # График 2: Позиция vs Релевантность
    scatter_colors = colors
    ax2.scatter(df['Позиция'], df['Релевантность'], c=scatter_colors, s=100, alpha=0.8)
    ax2.set_xlabel('Позиция в результатах поиска')
    ax2.set_ylabel('Релевантность')
    ax2.set_title('Зависимость релевантности от позиции')
    ax2.grid(True, alpha=0.3)
    
    # Добавляем аннотации для ключевых точек
    ax2.annotate('Выбранный\n(0000-...2165)', 
                xy=(9, 0.63), xytext=(15, 0.65),
                arrowprops=dict(arrowstyle='->', color='black'),
                fontsize=9, ha='center')
    
    ax2.annotate('Референсный\n(0000-...0599)', 
                xy=(40, 0.61), xytext=(35, 0.59),
                arrowprops=dict(arrowstyle='->', color='red'),
                fontsize=9, ha='center')
    
    plt.tight_layout()
    plt.savefig('orcid_ranking_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_algorithm_flowchart():
    """Создает блок-схему алгоритма"""
    
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Определяем блоки
    blocks = [
        {'text': 'Email поиск\nчерез Google API', 'pos': (2, 9), 'color': 'lightblue'},
        {'text': 'Извлечение ORCID\nиз веб-страниц', 'pos': (2, 7.5), 'color': 'lightgreen'},
        {'text': 'Для каждого ORCID:\nРасчет релевантности', 'pos': (2, 6), 'color': 'lightyellow'},
        {'text': 'Позиция\n(25%)', 'pos': (0.5, 4.5), 'color': 'lightcoral'},
        {'text': 'Прямой URL\n(20%)', 'pos': (1.5, 4.5), 'color': 'lightcoral'},
        {'text': 'Близость имени\n(15%)', 'pos': (2.5, 4.5), 'color': 'lightcoral'},
        {'text': 'Домен\n(15%)', 'pos': (3.5, 4.5), 'color': 'lightcoral'},
        {'text': 'Сортировка по\nрелевантности', 'pos': (2, 3), 'color': 'lightgreen'},
        {'text': 'Дополнительная логика:\nПредпочтение ORCID URL', 'pos': (2, 1.5), 'color': 'orange'},
        {'text': 'Выбор лучшего\nORCID', 'pos': (2, 0), 'color': 'gold'},
    ]
    
    # Рисуем блоки
    for block in blocks:
        rect = Rectangle((block['pos'][0]-0.4, block['pos'][1]-0.3), 0.8, 0.6, 
                        facecolor=block['color'], edgecolor='black', linewidth=1)
        ax.add_patch(rect)
        ax.text(block['pos'][0], block['pos'][1], block['text'], 
               ha='center', va='center', fontsize=9, fontweight='bold')
    
    # Рисуем стрелки
    arrows = [
        ((2, 8.7), (2, 8.1)),  # Email -> Извлечение
        ((2, 7.2), (2, 6.6)),  # Извлечение -> Расчет
        ((2, 5.4), (2, 5.1)),  # Расчет -> Факторы (начало)
        ((2, 4.8), (0.5, 4.8)), # К позиции
        ((2, 4.8), (1.5, 4.8)), # К URL
        ((2, 4.8), (2.5, 4.8)), # К имени
        ((2, 4.8), (3.5, 4.8)), # К домену
        ((2, 4.1), (2, 3.6)),  # Факторы -> Сортировка
        ((2, 2.7), (2, 2.1)),  # Сортировка -> Доп.логика
        ((2, 1.2), (2, 0.6)),  # Доп.логика -> Выбор
    ]
    
    for start, end in arrows:
        ax.annotate('', xy=end, xytext=start,
                   arrowprops=dict(arrowstyle='->', lw=1.5, color='darkblue'))
    
    ax.set_xlim(-1, 5)
    ax.set_ylim(-1, 10)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('🔬 Блок-схема алгоритма ранжирования ORCID', 
                fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig('orcid_algorithm_flowchart.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_name_analysis_chart():
    """Создает диаграмму анализа имен"""
    
    # Компоненты анализа близости имени
    components = ['Прямая проверка\nв URL', 'Контекстный анализ\nвеб-страницы', 
                 'ORCID API\n(для прямых URL)', 'Анализ вариаций\nимени', 'Паттерны ORCID']
    weights = [0.4, 0.6, 0.8, 0.3, 0.2]
    example_scores = [0.1, 0.2, 0.5, 0.0, 0.1]  # Примерные значения для нашего случая
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # График 1: Веса компонентов
    bars1 = ax1.bar(components, weights, color='skyblue', alpha=0.7)
    ax1.set_ylabel('Вес компонента')
    ax1.set_title('Веса компонентов анализа близости имени')
    ax1.set_xticklabels(components, rotation=45, ha='right')
    ax1.grid(True, alpha=0.3)
    
    # Добавляем значения
    for bar in bars1:
        height = bar.get_height()
        ax1.annotate(f'{height:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')
    
    # График 2: Пример расчета
    bars2 = ax2.bar(components, example_scores, color='lightgreen', alpha=0.7)
    ax2.set_ylabel('Оценка компонента')
    ax2.set_title('Пример оценок для "Марапов Дамир Ильдарович"')
    ax2.set_xticklabels(components, rotation=45, ha='right')
    ax2.grid(True, alpha=0.3)
    
    # Добавляем значения
    for bar in bars2:
        height = bar.get_height()
        ax2.annotate(f'{height:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('orcid_name_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
    """Главная функция для создания всех графиков"""
    
    print("🔬 Создание визуализации алгоритма ранжирования ORCID...")
    
    # Создаем все графики
    print("📊 Создание диаграммы распределения весов...")
    create_weight_distribution_chart()
    
    print("🧮 Создание примера расчета релевантности...")
    create_scoring_example()
    
    print("📈 Создание сравнения ранжирования...")
    create_ranking_comparison()
    
    print("🔄 Создание блок-схемы алгоритма...")
    create_algorithm_flowchart()
    
    print("📝 Создание анализа имен...")
    create_name_analysis_chart()
    
    print("✅ Все графики созданы!")
    print("\nСозданные файлы:")
    print("- orcid_weights_distribution.png")
    print("- orcid_scoring_example.png") 
    print("- orcid_ranking_comparison.png")
    print("- orcid_algorithm_flowchart.png")
    print("- orcid_name_analysis.png")

if __name__ == "__main__":
    main()
