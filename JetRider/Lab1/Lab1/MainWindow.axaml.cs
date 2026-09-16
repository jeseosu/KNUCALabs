using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Styling;
using ScottPlot;

namespace Lab1;

public partial class MainWindow : Window
{
    private ObservableCollection<ResultItem> _results;

    public MainWindow()
    {
        InitializeComponent();
        _results = new ObservableCollection<ResultItem>();
        DgResults.ItemsSource = _results;
        ChartPlot.Refresh();
    }

    private void BtnCalculate_OnClick(object? sender, RoutedEventArgs e)
    {
        try
        {
            double xn = Convert.ToDouble(TbXn.Text.Replace(".", ","));
            double xk = Convert.ToDouble(TbXk.Text.Replace(".", ","));
            double h = Convert.ToDouble(TbH.Text.Replace(".", ","));
            double a = Convert.ToDouble(TbA.Text.Replace(".", ","));

            _results.Clear();
            ChartPlot.Plot.Clear();

            List<double> xValues = new List<double>();
            List<double> yValues = new List<double>();
            
            for (double x = xn; x <= xk; x += h)
            {
                double y = CalculateFunction(x, a);
                
                _results.Add(new ResultItem(x, y));
                xValues.Add(x);
                yValues.Add(y);
            }
            
            if (xValues.Count > 0)
            {

                var scatter = ChartPlot.Plot.Add.Scatter(xValues.ToArray(), yValues.ToArray());
                scatter.Color = ScottPlot.Colors.Blue; 
                ChartPlot.Plot.Title("Графік функції f(x)");
                ChartPlot.Plot.XLabel("X");
                ChartPlot.Plot.YLabel("Y");
                ChartPlot.Plot.Axes.AutoScale();
                ChartPlot.Refresh();
            }
        }
        catch (FormatException)
        {
            
        }
    }
    
    private double CalculateFunction(double x, double a)
    {
        if (x <= 0)
        {
            // f1(x) = |x|^5 * ctg(x+2)
            // ctg(x) = 1 / tg(x)
            return Math.Pow(Math.Abs(x), 5) * (1.0 / Math.Tan(x + 2));
        }
        if (x > 0 && x <= a)
        {
            // f2(x) = (5x + x^2) / (x^2 + 3)^3
            return (5 * x + Math.Pow(x, 2)) / Math.Pow(Math.Pow(x, 2) + 3, 3);
        }
        
        // f3(x) = sin^2(x+3)
        return Math.Pow(Math.Sin(x + 3), 2);
    }
}