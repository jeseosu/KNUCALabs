using System;

namespace Lab1;

public class ResultItem
{
    public double X { get; set; }
    public double Y { get; set; }

    public ResultItem(double x, double y)
    {
        X = Math.Round(x, 4);
        Y = Math.Round(y, 4);
    }
}