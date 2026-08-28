const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const CopyWebpackPlugin = require("copy-webpack-plugin");

module.exports = {
  mode: "development",
  entry: "./src/index.tsx",
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "[name].[contenthash].js",
    chunkFilename: "[name].[contenthash].chunk.js",
    publicPath: "/static/",
    clean: true,
  },
  resolve: {
    extensions: [".ts", ".tsx", ".js", ".jsx"],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: {
          loader: "ts-loader",
          options: { onlyCompileBundledFiles: true },
        },
        exclude: /node_modules/,
      },
      {
        test: /\.css$/,
        use: ["style-loader", "css-loader"],
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: "./template.html",
      favicon: "./public/favicon.ico",
    }),
    new CopyWebpackPlugin({
      patterns: [
        {
          from: path.resolve(__dirname, "vendor/live2d"),
          to: "live2d",
        },
      ],
    }),
  ],
  optimization: {
    splitChunks: {
      chunks: "all",
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/](?!l2d(?:$|[\\/]))/,
          name: "vendor",
          chunks: "all",
        },
      },
    },
  },
  devServer: {
    port: 3000,
    hot: true,
    historyApiFallback: { index: "/static/index.html" },
    proxy: [
      { context: ["/ws"], target: "http://localhost:8000", ws: true },
      { context: ["/auth", "/admin", "/media", "/tasks", "/messaging", "/news", "/attachments", "/uploads", "/activities", "/reviews", "/about", "/exam_board", "/tutorials", "/recruitment", "/site-policy"], target: "http://localhost:8000" },
    ],
  },
};
